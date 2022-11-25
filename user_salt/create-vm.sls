# -*- coding: utf-8 -*-
# vim: set syntax=yaml ts=2 sw=2 sts=2 et :

{{salt['pillar.get']('vm_name')}}-present:
  qvm.present:
    - name: {{salt['pillar.get']('vm_name')}}
    - template: {{salt['pillar.get']('vm_template')}}
    - label: {{salt['pillar.get']('label')}}

{{salt['pillar.get']('vm_name')}}-prefs:
  qvm.prefs:
    - name: {{salt['pillar.get']('vm_name')}}
    - netvm: {{salt['pillar.get']('netvm')}}
    - memory: {{salt['pillar.get']('memory')}}
    - maxmem: {{salt['pillar.get']('maxmem')}}
