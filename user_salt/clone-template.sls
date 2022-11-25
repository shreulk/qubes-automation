# -*- coding: utf-8 -*-
# vim: set syntax=yaml ts=2 sw=2 sts=2 et :

{{salt['pillar.get']('template')}}-clone:
  qvm.clone:
    - name: {{salt['pillar.get']('template')}}
    - source: {{salt['pillar.get']('template_parent')}}
