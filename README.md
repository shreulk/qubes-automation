# Qubes Automation

## What?
This is a Python script for creating custom Qubes VM configs with inheritable properties

You can regenerate (delete and recreate) a VM based on a small config script if you think something is wrong with it

### Pros

- Define configurations imperatively using Python
- Inheritable configuration options
- Regenerate qubes effortlessly if compromised or broken
- Minimal attack surface: just a single Python script with no additional dependencies

### Cons

- Maybe not suitable for production use
- Needs optimization

## Why?
I hate salt.

## Where?
https://github.com/shreulk/qubes-automation

## Who?
Here is my gpg signing key fingerprint: 90ACF978744E65FC8E326D979311DD635B24B4A7

## How?
1. Download the repo
2. Copy to dom0 (or check and type it by hand if you are paranoid)
3. Run `./install` or perform the commands inside it manually step by step
4. Create a `qaconf.py` file. See below for an example.

How to copy a file to dom0 (WARNING: maybe dangerous):
```bash
dispXXXX$ git clone https://github.com/shreulk/qubes-automation
dom0# qvm-run --pass-io dispXXXX 'cat qubes-automation/qa.py > qa.py'
```

Copy to dom0 using split git (Maybe more secure): https://github.com/woju/qubes-app-split-git

## Example

See `example/` directory.

## Alternatives
- salt (built in, difficult to set inherited configuration options)
- qubes-ansible (easier to use, requires installing and building software in dom0)

## License
AGPL3+

## Donate
- XMR:
- BTC:


