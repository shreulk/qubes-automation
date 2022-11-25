# -*- coding: utf-8 -*-
# vim: set syntax=yaml ts=2 sw=2 sts=2 et :

{{salt['pillar.get']('file_name')}}:
  file.managed:
    - source: salt://user_salt/files/{{salt['pillar.get']('salt_file')}}
    - user: {{salt['pillar.get']('user')}}
    - group: {{salt['pillar.get']('group')}}
    - mode: {{salt['pillar.get']('mode')}}
    - makedirs: True
    - show_changes: True
