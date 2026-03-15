# VirtualBox VM Setup for Testing

Quick guide to setting up a local Ubuntu Server VM for testing Qualify.

## 1. Create the VM

In VirtualBox, create a new VM with **Ubuntu 24.04 Server** using the unattended install wizard.

Suggested settings:
- Username: `vboxuser` (or any user)
- Set a password — you'll use this as the sudo password in Qualify
- Host Name: `ubuntu` (doesn't matter)
- Domain Name: leave as-is (`myguest.virtualbox.org`)

## 2. Network — Add a Host-Only Adapter

This gives the VM a stable IP reachable from both Windows and WSL.

1. **File → Tools → Network Manager**
   - Create a Host-Only network if none exists
   - Adapter tab: `192.168.56.1 / 255.255.255.0`
   - DHCP Server tab: Enable, range `192.168.56.101–254`

2. **VM Settings → Network → Adapter 2**
   - Enable → Attached to: **Host-Only Adapter**

## 3. Configure Static IP in the VM

After first boot, open the VM console and edit netplan:

```bash
sudo nano /etc/netplan/50-cloud-init.yaml
```

```yaml
network:
  ethernets:
    enp0s3:
      dhcp4: true
    enp0s8:
      dhcp4: no
      addresses:
        - 192.168.56.101/24
  version: 2
```

```bash
sudo netplan apply
```

## 4. Install SSH Server

```bash
sudo apt update
sudo apt install openssh-server
sudo systemctl enable --now ssh
```

No firewall setup needed for local testing.

## 5. Verify SSH Access

From WSL:
```bash
ssh vboxuser@192.168.56.101
```

From Windows PowerShell:
```powershell
ssh vboxuser@192.168.56.101
```

## 6. Add to Qualify

In the Qualify UI → Servers → Add Server:

| Field | Value |
|-------|-------|
| Name | `virtualbox-test` (or any label) |
| Host | `192.168.56.101` |
| Port | `22` |
| User | `vboxuser` |
| SSH Key Path | `~/.ssh/id_rsa` (or your key) |
| Sudo Password | your VM password |

Qualify will try key auth first, then fall back to password if the key isn't authorized on the VM.
