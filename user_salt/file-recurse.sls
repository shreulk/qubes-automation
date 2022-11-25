# -*- coding: utf-8 -*-
# vim: set syntax=yaml ts=2 sw=2 sts=2 et :

{{salt['pillar.get']('file_name')}}:
  file.recurse:
    - source: salt://user_salt/files/{{salt['pillar.get']('salt_file')}}
    - user: {{salt['pillar.get']('user')}}
    - group: {{salt['pillar.get']('group')}}
    - dir_mode: {{salt['pillar.get']('dir_mode')}}
    - file_mode: {{salt['pillar.get']('file_mode')}}
    - show_changes: True
