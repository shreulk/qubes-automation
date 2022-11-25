#!/usr/bin/env python3
# qubes-automation: A python script to automate qubes configuration
# Copyright (C) 2022  shreulk@proton.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


from collections import OrderedDict
import os
import shutil
import subprocess
from typing import Dict, Iterable, List, Literal, Optional, Tuple, Union
import sys
import time

# Custom type names
LabelColor = str
LABEL_COLORS = [ "red", "orange", "yellow", "green", "gray", "blue", "purple", "black" ]
TEMPLATE_COLOR = "gray"
DEFAULT = "default"
Default = Literal[DEFAULT]
VMName = str
NetVM = Optional[Union[Default, VMName]]
VirtMode = Union[Default, Literal["pvh", "hvm"]]

# Terminal Colors
class TC:
    # https://stackoverflow.com/questions/287871/how-to-print-colored-text-to-the-terminal
    PURPLE = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    VM = YELLOW
    FILE = BLUE
    COMMAND = GREEN
    ERROR = RED
    def red(s: str) -> str:
        return TC.RED + s + TC.END
    def green(s: str) -> str:
        return TC.GREEN + s + TC.END
    def bold(s: str) -> str:
        return TC.BOLD + s + TC.END
    def vm(s: str) -> str:
        return TC.VM + s + TC.END
    def file(s: str) -> str:
        return TC.FILE + s + TC.END
    def command(s: str) -> str:
        return TC.COMMAND + s + TC.END
    def error(s: str) -> str:
        return TC.ERROR + s + TC.END


def exit_failure(message=None):
    if message is not None:
        print(message)
    print("Exit.")
    sys.exit(1)

def run(command: List[str], exit_on_failure=False):
    print("Running command", TC.command(" ".join(command)))
    p = subprocess.run(command)
    if p.returncode != 0:
        print(f"command {command} {TC.error(f'returned exit code {p.returncode}')}")
        if exit_on_failure:
            exit_failure(None)
def get_stdout(command: List[str]) -> str:
    return subprocess.check_output(command, universal_newlines=True).strip()

# Abstract state that can be checked for differences and fixed.
# Only check() needs to be implemented.
class State:
    # Returns true if the current state is inconsistent with the configuration.
    def check(self, fix: bool = False) -> bool:
        raise NotImplementedError("Override check function")
    def apply(self) -> None:
        self.check(fix=True)
    def set_name(self, name: VMName):
        self.name = name
        return self
    def get_name(self) -> str:
        return self.name

class PCIDevice(State):
    # Must call set_name() before check() or attach()
    def __init__(self, device_name: str, no_strict_reset=False):
        self.device_name = device_name
        self.command = ["qvm-pci", "attach", "--persistent"]
        if no_strict_reset:
            self.command.append("-ono-strict-reset=True")
    def attach(self):
        run(self.command + [self.get_name(), self.device_name], exit_on_failure=False)
    def check(self, fix: bool = False):
        needs_update = False
        current_pci_devices = get_stdout(['qvm-pci', 'list', self.get_name()]).splitlines()
        current_pci_devices = [p.split()[0] for p in current_pci_devices]
        if self.device_name not in current_pci_devices:
            print(f"VM {self.get_name()} does not have a PCI device attached {self.device_name}")
            needs_update = True
        if needs_update and fix:
            self.attach()
        return needs_update

class AppMenu(State):
    def __init__(self, appmenu: Union[str, List[str]]):
        if type(appmenu) == str:
            if appmenu.find("\\n") != -1:
                self.appmenu_list = appmenu.split("\n")
            elif appmenu.find("\n") != -1:
                self.appmenu_list = appmenu.split("\n")
            else:
                self.appmenu_list = [appmenu]
        else:
            self.appmenu_list = appmenu
    def check(self, fix=False) -> bool:
        needs_update = False
        current_appmenus = get_stdout(["qvm-appmenus", "--get-whitelist", self.get_name()]).splitlines()
        if sorted(current_appmenus) != sorted(self.appmenu_list):
            needs_update = True
            print(f"VM {self.get_name()} has appmenu {current_appmenus} and not {self.appmenu_list}")
            if fix:
                SetAppMenu(self.get_name(), "\\n".join(self.appmenu_list)).run()
        return needs_update

class QVMFeatures(State):
    # Must call set_name() before check()
    def __init__(self, dictionary):
        self.features = dictionary
    def check(self, fix=False) -> bool:
        needs_update = False
        for feature_name, value in self.features.items():
            check_command = ["qvm-features", self.get_name(), feature_name]
            try:
                current_value = get_stdout(check_command)
            except:
                current_value = None
            value = str(value)
            if current_value != value:
                print(f"VM {TC.vm(self.get_name())} feature {feature_name} is {current_value} not {value}")
                needs_update = True
                if fix:
                    print(f"{TC.bold('Setting')} VM {TC.vm(self.get_name())} feature {feature_name} from {current_value} to {value}")
                    command = check_command + [value]
                    run(command, exit_on_failure=True)
        return needs_update

class QVMTags(State):
    # Must call set_name() before check()
    def __init__(self, tags: List[str] = []):
        self.tags = tags
    def check(self, fix=False) -> bool:
        needs_update = False
        current_tags = get_stdout(["qvm-tags", self.get_name(), "list"]).splitlines()
        for tag in self.tags:
            if tag not in current_tags:
                needs_update = True
                print(f"VM {TC.vm(self.get_name())} does not have tag {tag}")
                if fix:
                    print(f"{TC.bold('Setting')} VM {TC.vm(self.get_name())} tag {tag}")
                    run(["qvm-tags", self.get_name(), "add", tag], exit_on_failure=True)
        return needs_update

class QVMPrefs(State):
    # Set maxmem to 0 for no in-memory balancing
    # Must call set_name() before check()
    def __init__(self, color: LabelColor, netvm: Union['VM', NetVM] = None, virt_mode: VirtMode = DEFAULT, autostart=False, provides_network=False, max_memory: Union[Default, int] = DEFAULT, start_memory: Union[Default, int] = DEFAULT):
        if virt_mode == DEFAULT:
            virt_mode = "pvh"
        if max_memory == DEFAULT:
            max_memory = 4000
        elif max_memory == None:
            max_memory = 0
        if start_memory == DEFAULT:
            start_memory = 400
        self.prefs = {
                "virt_mode": virt_mode,
                "autostart": autostart,
                "provides_network": provides_network,
                "maxmem": max_memory,
                "memory": start_memory,
        }
        self.set_label(color)
        self.set_netvm(netvm)
    def set_label(self, label: LabelColor):
        self.prefs["label"] = label
    def get_label(self) -> LabelColor:
        return self.prefs["label"]
    def set_netvm(self, netvm: Union['VM', NetVM]):
        if netvm is None:
            netvm = ""
        elif isinstance(netvm, VM):
            netvm = netvm.get_name()
        self.prefs["netvm"] = netvm
    def get_netvm(self) -> Union['VM', NetVM]:
        return self.prefs["netvm"]
    def set_anonymous(self):
        pass
        #self.prefs["keyboard_layout"] = "us++"
        #raise Exception("Cannot set a custom keyboard layout. See https://github.com/QubesOS/qubes-issues/issues/6920")
    def set_template_for_dispvms(self, template_for_dispvms: bool):
        self.prefs["template_for_dispvms"] = template_for_dispvms
    def check(self, fix=False) -> bool:
        needs_update = False
        for pref_name, value in self.prefs.items():
            check_command = ["qvm-prefs", self.get_name(), pref_name]
            current_value = get_stdout(check_command)
            value = str(value)
            if current_value != value:
                print(f"VM {TC.vm(self.get_name())} pref {pref_name} is {current_value} not {value}")
                needs_update = True
                if fix:
                    print(f"{TC.BOLD}Setting{TC.END} VM {TC.vm(self.get_name())} pref {pref_name} from {current_value} to {value}")
                    command = check_command + [value]
                    run(command, exit_on_failure=True)
        return needs_update


# Abstract class for custom salt scripts to manage VMs from disposable management VMs
# Each subclass must define self.user_salt_name and self.pillar
class QubesCtl:
    USER_PILLAR_NAME = "target_pillar"
    USER_PILLAR = f"/srv/user_pillar/{USER_PILLAR_NAME}.sls"
    USER_PILLAR_TOP = "/srv/user_pillar/top.sls" 
    # Set target to None to use dom0 as the management VM
    def set_target(self, target: VMName):
        self.target = target
    def get_salt(self):
        # Files in /srv/salt/user_salt/
        return f"user_salt.{self.user_salt_name}"
    def format_pillar(self):
        return f"pillar={str(self.pillar)}"
    def run(self):
        if self.target is None:
            run(["sudo", "qubesctl", "--show-output", "state.sls", self.get_salt(), self.format_pillar()], exit_on_failure=True)
        else:
            print("Writing to", TC.file(QubesCtl.USER_PILLAR))
            with open(QubesCtl.USER_PILLAR, 'w') as f:
                for key, value in self.pillar.items():
                    # Jinja
                    #f.write(f"{{%- set {key} = '{value}' %}}\n")
                    # Salt
                    f.write(f"{key}: {value}\n")
                    print(f"    {self.user_salt_name} Pillar {key}={value}")
            # Assumes application is single-threaded
            with open(QubesCtl.USER_PILLAR_TOP, 'r') as f:
                old_top = f.read()
            with open(QubesCtl.USER_PILLAR_TOP, 'a') as f:
                f.write(f"  {self.target}:\n    - {QubesCtl.USER_PILLAR_NAME}")
            try:
                run(["sudo", "qubesctl", "--show-output", "--skip-dom0", f"--targets={self.target}", "state.sls", self.get_salt()], exit_on_failure=True)
            finally:
                print(f"Removing {TC.file(QubesCtl.USER_PILLAR)}")
                with open(QubesCtl.USER_PILLAR, 'w') as f:
                    f.write("")
                with open(QubesCtl.USER_PILLAR_TOP, 'w') as f:
                    f.write(old_top)

class CloneTemplate(QubesCtl):
    def __init__(self, name: VMName, template_cloned_from: VMName):
        assert VM.exists(template_cloned_from)
        if VM.is_root_template(name):
            assert root_template == name == template_cloned_from
        self.user_salt_name = "clone-template"
        self.target = None
        self.pillar = {
                "template": name,
                "template_parent": template_cloned_from,
        }
class CreateVM(QubesCtl):
    def __init__(self, name: VMName, template: VMName, qvm_prefs: QVMPrefs):
        assert VM.exists(template)
        self.user_salt_name = "create-vm"
        self.target = None
        self.pillar = {
                "vm_name": name,
                "vm_template": template,
                "netvm": qvm_prefs.prefs["netvm"],
                "label": qvm_prefs.prefs["label"],
                "memory": qvm_prefs.prefs["memory"],
                "maxmem": qvm_prefs.prefs["maxmem"],
                #"default_dispvm": DEFAULT,
                #"appmenu": appmenu,
        }
class SetAppMenu(QubesCtl):
    def __init__(self, name: str, appmenu: str):
        self.user_salt_name = "appmenus"
        self.target = None
        self.pillar = {
                "vm_name": name,
                "appmenu": appmenu
        }
class VMService(QubesCtl):
    def __init__(self, name: VMName, enabled_services: List[str]):
        self.user_salt_name = "vm-service"
        self.target = None
        self.pillar = {
                "vm_name": name,
                "enabled": ",".join(enabled_services)
        }
class InstallPackage(QubesCtl):
    def __init__(self, target_vm: VMName, packages: List[str]):
        self.user_salt_name = "install"
        self.target = target_vm
        self.pillar = { "packages": ",".join(packages) }
class Upgrade(QubesCtl):
    def __init__(self):
        self.user_salt_name = "upgrade"
        self.pillar = {}
class FileManage(QubesCtl):
    def __init__(self, file_name: str, salt_file: str, user: str = "root", mode: str = "644"):
        self.user_salt_name = "file-manage"
        assert os.path.exists(f"/srv/salt/user_salt/files/{salt_file}")
        self.pillar = {
                "file_name": file_name,
                "salt_file": salt_file,
                "user": user,
                "group": user,
                "mode": mode,
        }
class CopyRecursively(QubesCtl):
    def __init__(self, directory: str, salt_dir: str, user: str, dir_mode: str, file_mode: str):
        self.user_salt_name = "file-recurse"
        self.pillar = {
                "file_name": directory,
                "salt_file": salt_dir,
                "user": user,
                "group": user,
                "dir_mode": dir_mode,
                "file_mode": file_mode,
        }
class FileSymlink(QubesCtl):
    def __init__(self, file_name: str, symlink: str):
        self.user_salt_name = "file-symlink"
        self.pillar = {
                "file_name": file_name,
                "symlink_path": symlink,
        }
class RunCommand(QubesCtl):
    def __init__(self, command: str, user: str = "root"):
        self.user_salt_name = "run-command"
        self.pillar = {
                "command": command,
                "user": user
        }


# Abstract class for VM types
class VM(State):
    SUPPORTED_OPERATING_SYSTEMS = {
            "debian": {"versions": [10, 11], "default_appmenu": ["debian-xterm.desktop"]},
            "fedora": {"versions": [32, 34], "default_appmenu": ["xterm.desktop"]},
            "whonix-ws": {"versions": [16], "default_appmenu": ["janondisttorbrowser.desktop", "anondist-torbrowser_update.desktop", "whonixcheck.desktop", "xfce4-terminal.desktop"]},
            "whonix-gw": {"versions": [16], "default_appmenu": ["anon_connection_wizard.desktop", "gateway-arm.desktop", "gateway-reloadtor.desktop", "restart-tor-gui.desktop", "sdwdate-gui.desktop", "gateway-stoptor.desktop", "Thunar.desktop", "tor-control-panel.desktop", "gateway-tordata.desktop", "gateway-torrcexamples.desktop", "gateway-torrc.desktop", "whonixcheck.desktop", "xfce4-terminal.desktop"]},
    }
    ALL_VMS = []
    def add_vm(vm):
        VM.ALL_VMS.append(vm)
    def get_vms() -> OrderedDict:
        return OrderedDict([(vm.get_name(), vm) for vm in VM.ALL_VMS])
    def exists(name) -> bool:
        all_vms = get_stdout(["qvm-ls", "--raw-data", "--fields", "NAME"]).splitlines()
        return name in all_vms
    def vm_running(name) -> bool:
        running_vms = get_stdout(["qvm-ls", "--raw-data", "--running", "--fields", "NAME"]).splitlines()
        return name in running_vms
    def vm_shutdown(name):
        print("Shutting down", name)
        run(["qvm-shutdown", "--wait", name], exit_on_failure=True)
    def vm_updateable(name):
        try:
            return get_stdout(["qvm-features", name, "updates-available"]) == "1"
        except:
            return False
    def get_vms_connected_to(netvm_name) -> List[VMName]:
        vms_and_netvms = get_stdout(["qvm-ls", "--raw-data", "--fields", "NAME,NETVM"]).splitlines()
        connected_vms = []
        for vm_and_netvm in vms_and_netvms:
            if vm_and_netvm.endswith(f"|{netvm_name}"):
                connected_vms.append(vm_and_netvm.split("|")[0])
        return connected_vms
    def root_templates() -> List[VMName]:
        return [f"{os_name}-{os_version}{minimal}"
                for os_name in VM.SUPPORTED_OPERATING_SYSTEMS
                for os_version in VM.SUPPORTED_OPERATING_SYSTEMS[os_name]["versions"]
                for minimal in ["", "-minimal"]
        ]
    def is_root_template(name: VMName) -> bool:
        return name in VM.root_templates()
    def default_root_template(os="debian", minimal=True) -> VMName:
        version = VM.SUPPORTED_OPERATING_SYSTEMS[os]["versions"][-1]
        if minimal:
            minimal_str = "-minimal"
        else:
            minimal_str = ""
        return f"{os}-{versoin}{minimal_str}"
    def default_appmenu(vm: 'VM', default=[]) -> Optional[str]:
        if default == []:
            vm_name = vm.root_template().get_name()
            if VM.is_root_template(vm_name):
                for os in VM.SUPPORTED_OPERATING_SYSTEMS.keys():
                    if vm_name.startswith(os):
                        return VM.SUPPORTED_OPERATING_SYSTEMS[os]["default_appmenu"]
        return default
    def get_updatevm() -> str:
        return get_stdout(["qubes-prefs", "updatevm"])
    def temporary_alternative_template_to(name: VMName) -> VMName:
        default_template = VM.default_root_template(minimal=False)
        default_minimal_template = VM.default_root_template(minimal=True)
        if VM.is_root_template(name):
            if name == default_minimal_template:
                return default_template
            else:
                return default_minimal_template
        else:
            return default_minimal_template

    # Presalts are run before packages are installed
    def add_presalt(self, salt: QubesCtl):
        self.presalts.append(salt)
    def apply_presalts(self):
        for salt in self.presalts:
            salt.set_target(self.get_name())
            salt.run()
    # Salts are run after packages are installed
    def add_salt(self, salt: QubesCtl):
        self.salts.append(salt)
    # FIXME: apply_salt and apply_presalts must be single threaded
    # because there is no deep copy when using get_subclass_salts() and TemplateVM.cloned()
    def apply_salts(self):
        for salt in self.salts:
            salt.set_target(self.get_name())
            salt.run()
    # Subclass Salts are not called in TemplateVMs
    # Subclass Salts are called in AppVMs that use a TemplateVM
    def add_subclass_salt(self, salt: QubesCtl):
        self.subclass_salts.append(salt)
    def get_subclass_salts(self) -> List[QubesCtl]:
        return self.subclass_salts
    def root_template(self) -> 'VM':
        raise NotImplementedError("Override root_template function")
    def is_running(self) -> bool:
        return VM.vm_running(self.get_name())
    def is_updateable(self) -> bool:
        return VM.vm_updateable(self.get_name())
    def shutdown(self):
        return VM.vm_shutdown(self.get_name())

class TemplateVM(VM):
    def __init__(self, name: VMName, cloned_from: Optional['TemplateVM'], qvm_prefs: Optional[QVMPrefs], packages: List[str]):
        VM.add_vm(self)
        self.name = name
        self.presalts = []
        self.salts = []
        self.subclass_salts = []
        self.cloned_templates = []
        if qvm_prefs is not None:
            self.qvm_prefs = qvm_prefs
            self.qvm_prefs.set_label(TEMPLATE_COLOR)
        else:
            self.qvm_prefs = QVMPrefs(TEMPLATE_COLOR).set_name(name)
        self.qvm_prefs.set_netvm(None)
        self.cloned_from = cloned_from
        if cloned_from is None:
            assert name in VM.root_templates()
        self.packages = packages
        self.qvm_features = QVMFeatures({}).set_name(name)
    def cloned(self, name, packages: List[str], subclass_salts=True) -> 'TemplateVM':
        new_template = TemplateVM(name, self, None, self.packages + packages)
        for salt in self.presalts:
            new_template.add_presalt(salt)
        for salt in self.salts:
            new_template.add_salt(salt)
        if subclass_salts:
            for salt in self.subclass_salts:
                new_template.add_subclass_salt(salt)
        self.cloned_templates.append(new_template)
        return new_template
    def root_template(self) -> VM:
        if self.cloned_from is None:
            return self
        else:
            return self.cloned_from.root_template()
    def install_packages(self):
        if len(self.packages) > 0:
            updatevm = VM.get_updatevm()
            updatevm_running = VM.vm_running(updatevm)
            print(f"Ensuring template {TC.vm(self.get_name())} has installed {self.packages}")
            InstallPackage(self.get_name(), self.packages).run()
            if not updatevm_running:
                VM.vm_shutdown(updatevm)
    def upgrade(self):
        updatevm = VM.get_updatevm()
        updatevm_running = VM.vm_running(updatevm)
        print(f"Upgrading template {TC.vm(self.get_name())}")
        upgrade = Upgrade()
        upgrade.set_target(self.get_name())
        upgrade.run()
        if not updatevm_running:
            VM.vm_shutdown(updatevm)
    def check(self, fix=False):
        needs_update = False
        if not VM.exists(self.get_name()):
            needs_update = True
            print(f"Template {TC.vm(self.get_name())} does not exist")
            if fix:
                if self.cloned_from is not None:
                    print(f"Cloning template {TC.vm(self.cloned_from.get_name())} to {TC.vm(self.get_name())}")
                    CloneTemplate(self.get_name(), self.cloned_from.name).run()
                else:
                    # Call qubes /srv/formulas/base/virtual-machines-formula/qvm sls files
                    # Or use the new qvm-template cli
                    exit_failure(f"Will not create root template {self.get_name()}. Do it yourself.")
            else:
                return needs_update
        if fix:
            self.apply_presalts()
            self.install_packages()
            self.upgrade()
        needs_update |= self.qvm_prefs.check(fix=fix)
        if fix:
            self.apply_salts()
        return needs_update
    def regenerate(self, all_vms: Dict[str, VM]):
        if not VM.exists(self.get_name()):
            print(TC.vm(self.get_name()), "does not exist")
            self.apply()
            return
        if self.root_template() is self:
            run(["qubes-dom0-update", "--action=reinstall", "qubes-template-"+self.get_name()], exit_on_failure=True)
            self.apply()
        else:
            vms_with_self_as_template = [] # List[str]
            lines = get_stdout(["qvm-ls", "--raw-data", "--fields", "NAME,TEMPLATE"]).splitlines()
            for line in lines:
                if line.endswith(f"|{self.get_name()}"):
                    vms_with_self_as_template.append(line.split("|")[0])
            alternative_vm = VM.temporary_alternative_template_to(self.get_name())
            for vm_name in vms_with_self_as_template:
                vm = all_vms[vm_name]
                # Qubes cannot remove DispVMTemplate when there are DispVMs that use this as DispVM template
                if isinstance(vm, DispVMTemplate):
                    vm.get_dispvms(all_vms)
                    vm.remove_dispvms()
                print(f"Setting {TC.vm(vm_name)} template to {TC.vm(alternative_vm)}")
                run(["qvm-prefs", vm_name, "template", alternative_vm], exit_on_failure=True)
            print(TC.red("Removing"), TC.vm(self.get_name()))
            run(["qvm-remove", "--verbose", self.get_name()], exit_on_failure=True)
            print(TC.green("Regenerating"), TC.vm(self.get_name()))
            self.apply()
            for vm_name in vms_with_self_as_template:
                vm = all_vms[vm_name]
                print(f"Setting {TC.vm(vm_name)} template to {TC.vm(self.get_name())}")
                run(["qvm-prefs", vm_name, "template", self.get_name()], exit_on_failure=True)
                # Qubes cannot remove DispVMTemplate when there are DispVMs that use this as DispVM template
                if isinstance(vm, DispVMTemplate):
                    vm.create_dispvms()

class AppVM(VM):
    def __init__(self,
            name: VMName,
            template: TemplateVM,
            qvm_prefs: QVMPrefs,
            appmenu: List[str] = [],
            enabled_services=[],
            pci: List[PCIDevice] = [],
            template_for_dispvms: bool = False,
            tags: List[str] = [],
            qvm_features: Dict[str, str] = {},
            anonymous: bool = False
            ):
        VM.add_vm(self)
        self.name = name
        self.presalts = []
        self.salts = list(template.get_subclass_salts())
        self.subclass_salts = []
        self.template = template
        self.qvm_prefs = qvm_prefs.set_name(name)
        self.appmenu = AppMenu(VM.default_appmenu(self, default=appmenu)).set_name(name)
        self.enabled_services = enabled_services
        self.pci_devices = pci
        for pci_device in self.pci_devices:
            pci_device.set_name(name)
        qvm_features = {k:v for k, v in qvm_features.items()}
        if template_for_dispvms == True:
            self.qvm_prefs.set_template_for_dispvms(True)
            qvm_features["appmenus-dispvm"] = "1"
        if anonymous == True:
            self.qvm_prefs.set_anonymous()
            qvm_features["net.fake-ip"] = "192.168.0.2"
            qvm_features["net.fake-gateway"] = "192.168.0.1"
            qvm_features["net.fake-netmask"] = "255.255.255.0"
            qvm_features["no-monitor-layout"] = "True"
        self.qvm_features = QVMFeatures(qvm_features).set_name(name)
        self.tags = QVMTags(tags).set_name(name)
    def root_template(self) -> VM:
        return self.template.root_template()
    def check(self, fix=False):
        needs_update = False
        if not VM.exists(self.get_name()):
            needs_update = True
            print(f"VM {TC.vm(self.get_name())} does not exist")
            if fix:
                print("Creating VM", TC.vm(self.get_name()))
                if isinstance(self, DispVM):
                    run(["qvm-create", "--template", self.template.get_name(), "--class", "DispVM", "--label", self.qvm_prefs.get_label(), self.get_name()], exit_on_failure=True)
                else:
                    CreateVM(self.get_name(), self.template.get_name(), self.qvm_prefs).run()
                self.apply_presalts()
            else:
                return True
        needs_update |= self.appmenu.check(fix=fix)
        needs_update |= self.qvm_prefs.check(fix=fix)
        needs_update |= self.qvm_features.check(fix=fix)
        needs_update |= self.tags.check(fix=fix)
        # PCI Devices
        for pci_device in self.pci_devices:
            needs_update |= pci_device.check(fix=fix)
        # Services
        current_services = get_stdout(["qvm-service", "--list", self.get_name()]).splitlines()
        service_update = False
        for service in self.enabled_services:
            any_line_contains_service = False
            for line in current_services:
                if line.startswith(service) and line.endswith("on"):
                    any_line_contains_service = True
            if not any_line_contains_service:
                print(f"VM {self.get_name()} has not enabled service {service}")
                service_update = True
                needs_update = True
        if service_update and fix:
            VMService(self.get_name(), self.enabled_services).run()
        if fix:
            needs_update = True
            self.apply_salts()
        return needs_update

class DispVMTemplate(AppVM):
    # See superclass AppVM.__init__()
    def __init__(self, name: VMName, template: TemplateVM, qvm_prefs: Optional[QVMPrefs] = None):
        VM.add_vm(self)
        self.name = name
        self.presalts = []
        self.salts = list(template.get_subclass_salts())
        self.subclass_salts = []
        self.template = template
        if qvm_prefs is None:
            self.qvm_prefs = QVMPrefs(TEMPLATE_COLOR)
        else:
            self.qvm_prefs = qvm_prefs
        self.qvm_prefs.set_name(name)
        self.qvm_prefs.set_netvm(None)
        self.qvm_prefs.set_label(TEMPLATE_COLOR)
        self.qvm_prefs.set_template_for_dispvms(True)
        self.appmenu = AppMenu(VM.default_appmenu(self)).set_name(name)
        self.enabled_services = []
        self.pci_devices = []
        self.qvm_features = QVMFeatures({}).set_name(name)
        self.tags = QVMTags([]).set_name(name)
    def get_dispvms(self, all_vms: Dict[str, VM]):
        vms_with_self_as_template = [] # List[VM]
        netvms = {} # Dict[str, str]
        lines = get_stdout(["qvm-ls", "--raw-data", "--fields", "NAME,TEMPLATE"]).splitlines()
        for line in lines:
            if line.endswith(f"|{self.get_name()}"):
                vm_name = line.split("|")[0]
                vm_with_self_as_template = None
                for vm in all_vms.values():
                    if vm.get_name() == vm_name:
                        vm_with_self_as_template = vm
                if vm_with_self_as_template is None:
                    raise RuntimeError(TC.error("Cannot regenerate DispVM template"), TC.vm(self.get_name()), "because I don't know how to regenerate the DispVM", TC.vm(vm_name))
                elif not isinstance(vm_with_self_as_template, DispVM):
                    raise RuntimeError(TC.error("Cannot regenerate the AppVM template"), TC.vm(self.get_name()))
                vms_with_self_as_template.append(vm_with_self_as_template)
                for connected_vm in VM.get_vms_connected_to(vm_name):
                    netvms[connected_vm] = vm_name
        self.vms_with_self_as_template = vms_with_self_as_template
        self.dispvms_connected_vms = netvms
    # Must call self.get_dispvms() first
    def remove_dispvms(self):
        self.qubes_default_netvm = None
        self.qubes_default_clockvm = None
        default_netvm = get_stdout(["qubes-prefs", "default_netvm"])
        default_clockvm = get_stdout(["qubes-prefs", "clockvm"])
        for connected_vm, netvm in self.dispvms_connected_vms.items():
            print(TC.red("Removing"), "netvm", TC.vm(netvm), "from", TC.vm(connected_vm))
            # Set to none so that no updates are done without vpn connections
            run(["qvm-prefs", connected_vm, "netvm", ""], exit_on_failure=True)
        for vm in self.vms_with_self_as_template:
            if vm.get_name() == default_netvm:
                self.qubes_default_netvm = vm.get_name()
                run(["qubes-prefs", "default_netvm", ""])
            if vm.get_name() == default_clockvm:
                self.qubes_default_clockvm = vm.get_name()
                run(["qubes-prefs", "clockvm", ""])
            vm.shutdown()
            print(TC.red("Removing"), TC.vm(vm.get_name()))
            run(["qvm-remove", "--force", vm.get_name()], exit_on_failure=True)
    # Must call self.remove_dispvms() first
    def create_dispvms(self):
        for vm in self.vms_with_self_as_template:
            print(TC.green("Regenerating"), TC.vm(vm.get_name()))
            vm.apply()
            if self.qubes_default_netvm == vm.get_name():
                run(["qubes-prefs", "default_netvm", vm.get_name()])
            if self.qubes_default_clockvm == vm.get_name():
                run(["qubes-prefs", "clockvm", vm.get_name()])
        for connected_vm, netvm in self.dispvms_connected_vms.items():
            print("Setting netvm", TC.vm(netvm), "for", TC.vm(connected_vm))
            if VM.vm_running(connected_vm) and not VM.vm_running(netvm):
                run(["qvm-start", "--verbose", netvm])
            run(["qvm-prefs", connected_vm, "netvm", netvm], exit_on_failure=True)
    def regenerate(self, all_vms: Dict[str, VM]):
        if not VM.exists(self.get_name()):
            print(TC.vm(self.get_name()), "does not exist")
            self.apply()
            return
        # Qubes cannot remove DispVMTemplate when there are DispVMs that use this as DispVM template
        self.get_dispvms(all_vms)
        self.remove_dispvms()
        print(TC.red("Removing"), TC.vm(self.get_name()))
        run(["qvm-remove", "--verbose", self.get_name()], exit_on_failure=True)
        print(TC.green("Regenerating"), TC.vm(self.get_name()))
        self.apply()
        self.create_dispvms()

class DispVM(AppVM):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # DispVM has no salts. DispVMTemplate does.
        self.presalts = []
        self.salts = []
        self.subclass_salts = []
        self.qvm_features = QVMFeatures({"appmenus-dispvm":""}).set_name(self.get_name())
    def new_sys_net(name: VMName, template: DispVMTemplate, autostart: bool, pci: List[PCIDevice], sys_net_color="red") -> 'DispVM':
        qvm_prefs = QVMPrefs(sys_net_color, netvm=None, virt_mode="hvm", provides_network=True, autostart=autostart, max_memory=0, start_memory=300)
        qvm_prefs.set_name(name)
        return DispVM(name, template, qvm_prefs, pci=pci)
    def new_sys_firewall(name: VMName, color: LabelColor, template: DispVMTemplate, netvm: AppVM, autostart: bool) -> 'DispVM':
        qvm_prefs = QVMPrefs(color, netvm=netvm.get_name(), provides_network=True, autostart=autostart, max_memory=0, start_memory=300)
        qvm_prefs.set_name(name)
        return DispVM(name, template, qvm_prefs, qvm_features = {"qubes-firewall": "True"})
    def new_sys_usb(name: VMName, template: DispVMTemplate, autostart: bool, pci: List[PCIDevice], sys_usb_color="red") -> 'DispVM':
        qvm_prefs = QVMPrefs(sys_usb_color, netvm=None, virt_mode="hvm", provides_network=False, autostart=autostart, max_memory=0, start_memory=300)
        qvm_prefs.set_name(name)
        return DispVM(name, template, qvm_prefs, pci=pci)
    def new_sys_vpn(name: VMName, template: DispVMTemplate, netvm: VM, color: LabelColor) -> 'DispVM':
        qvm_prefs = QVMPrefs(color, netvm=netvm, provides_network=True, max_memory=0, start_memory=300)
        qvm_prefs.set_name(name)
        return DispVM(name, template, qvm_prefs)
    def check(self, fix=False):
        needs_update = super().check(fix=fix)
        needs_update |= self.qvm_features.check(fix)
        return needs_update
