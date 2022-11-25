from collections import OrderedDict
import time

from qa import TemplateVM, DispVM, AppVM, DispVMTemplate
from qa import InstallPackage, FileManage, CopyRecursively, FileSymlink, RunCommand
from qa import QVMPrefs, VM, PCIDevice

def config():
    SYS_VPN_APPVMS_COLOR = "yellow"
    DEFAULT_NETVM_APPVMS_COLOR = SYS_VPN_APPVMS_COLOR

    debian_11 = TemplateVM("debian-11", None, None, [])
    # Use add_salt to perform custom salt commands like adding files, installing packages, running commands,
    # Any template cloned from debian_11 will inherit its salts
    # The file apt/bullseye-main.list should be placed in /srv/salt/user_salt/files/apt/bullseye-main.list
    debian_11.add_salt(FileManage("/etc/apt/sources.list", "apt/bullseye-main.list", user="root", mode="644"))
    debian_11.add_salt(FileManage("/etc/mpv/mpv.conf", "mpv.conf", user="root", mode="644"))

    # Create a template VM for doing finance with.
    debian_11_bank = debian_11.cloned("debian-11-bank", None, None, [])
    debian_11_bank.add_salt(FileManage("/etc/apt/sources.list", "apt/bullseye-sid-main.list", user="root", mode="644"))
    debian_11_bank.add_salt(InstallPackage("debian-11-bank", ["banking-app"])
    bank = AppVM("bank", debian_11_bank, QVMPrefs(DEFAULT_NETVM_APPVMS_COLOR, netvm=DEFAULT_NETVM, start_memory=400, max_memory=1000), ["banking-app.desktop"])

    # Other templates
    whonix_gw_16 = TemplateVM("whonix-gw-16", None, None, [])
    whonix_ws_16 = TemplateVM("whonix-ws-16", None, None, [])
    debian_11_minimal = TemplateVM("debian-11-minimal", None, None, ["bzip2", "xz-utils", "zip", "unzip"])
    # subclass salts are run in all AppVMs that use this template
    debian_11_minimal.add_subclass_salt(FileManage("/rw/config/qubes-firewall-user-script", "firewall/qubes-firewall-user-script", user="root", mode="755"))

    # Signal VM
    # debian-11-minimal-signal is cloned from debian-11-minimal and contains all the same packages and files installed like bzip2
    debian_11_minimal_signal = debian_11_minimal.cloned("debian-11-minimal-signal", None, None, [])
    debian_11_minimal_signal.add_salt(RunCommand("curl -s -x 127.0.0.1:8082 https://updates.signal.org/desktop/apt/keys.asc | apt-key add -"))
    debian_11_minimal_signal.add_salt(FileManage("/etc/apt/sources.list", "apt/bullseye-main-signal", user="root", mode="644"))
    debian_11_minimal_signal.add_salt(InstallPackage(debian_11_minimal_signal.get_name(), ["signal-desktop"]))

    signal = AppVM("signal", debian_11_minimal_signal, QVMPrefs(DEFAULT_NETVM_APPVMS_COLOR, netvm=DEFAULT_NETVM, start_memory=400, max_memory=4000, autostart=True), ["signal-desktop.desktop"])

    # Sys USB
    # debian_11_minimal_sys_usb is a cloned copy of debian-11-minimal with the USB packages below installed
    debian_11_minimal_sys_usb = debian_11_minimal.cloned("debian-11-minimal-sys-usb", ["qubes-usb-proxy", "usbutils", "pciutils", "qubes-core-agent-passwordless-root", "qubes-u2f", "cryptsetup", "lvm2"])
    sys_usb_template = DispVMTemplate("sys-usb-template", debian_11_minimal_sys_usb)
    # Create a new sys-usb with 300M memory usage
    sys_usb = DispVM.new_sys_usb("sys-usb", sys_usb_template, autostart=True, pci=[PCIDevice("dom0:XX_XX.0", no_strict_reset=True)])

    return VM.get_vms()


def main():
    start_time = time.time()
    vms = config()

    # Create Signal VMs
    vms["debian-11-minimal-signal"].apply()
    vms["signal"].apply()

    # sys_usb template got corrupted or compromised: destroy and recreate VM
    vms["sys-usb-template"].regenerate()

    # Check all VMs configurations and update all updateable TemplateVMs
    for i, (name, vm) in enumerate(vms.items()):
    print(i, name)
    vm.check()
    if type(vm) == TemplateVM and vm.is_updateable():
        vm.upgrade()
    print()

    print("Time taken: ", int(time.time() - start_time))


