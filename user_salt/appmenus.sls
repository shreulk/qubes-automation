{% set gui_user = salt['cmd.shell']('groupmems -l -g qubes') %}
echo -e {{salt['pillar.get']('appmenu')}} | qvm-appmenus --set-whitelist - --update {{salt['pillar.get']('vm_name')}}:
  cmd.run:
    - requires: {{salt['pillar.get']('vm_name')}}
    - runas: {{gui_user}}
    #- onlyif: '[ qvm-appmenus --get-whitelist {{salt['pillar.get']('vm_name')}} != {{salt['pillar.get']('appmenu')}} ]'

