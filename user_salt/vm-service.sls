# -*- coding: utf-8 -*-
# vim: set syntax=yaml ts=2 sw=2 sts=2 et :

{{salt['pillar.get']('vm_name')}}-service:
  qvm.service:
    - name: {{salt['pillar.get']('vm_name')}}
    - enable: [{{salt['pillar.get']('enabled')}}]
