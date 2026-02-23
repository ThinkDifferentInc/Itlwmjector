#!/usr/bin/env python3

# Itlwmjector by ThinkDifferentInc (prodbyeternal)

import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import box
except ImportError:
    print("This script requires the 'rich' package. Install it with: pip install rich")
    sys.exit(1)

console = Console()
kernelname = platform.system()

if kernelname == "Darwin":
    console.print(f"[red]This utility does not work under macOS.[/red]")
    sys.exit(1)

# Scrape logic

def get_wifi_windows():
    networks = []
    try:
        profiles = subprocess.check_output(
            ["netsh", "wlan", "show", "profiles"], encoding="utf-8", errors="ignore"
        )
        for line in profiles.splitlines():
            if "All User Profile" in line:
                ssid = line.split(":")[1].strip()
                try:
                    details = subprocess.check_output(
                        ["netsh", "wlan", "show", "profile", ssid, "key=clear"],
                        encoding="utf-8",
                        errors="ignore",
                    )
                    for d in details.splitlines():
                        if "Key Content" in d:
                            password = d.split(":")[1].strip()
                            networks.append((ssid, password))
                            break
                except:
                    continue
    except Exception as e:
        console.print(f"[red]Error reading Windows Wi-Fi: {e}[/red]")
    return networks

def get_wifi_linux():
    networks = []
    try:
        connections = subprocess.check_output(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], encoding="utf-8"
        )
        for line in connections.splitlines():
            name, ctype = line.split(":")
            if ctype != "wifi":
                continue
            try:
                password = subprocess.check_output(
                    ["nmcli", "-s", "-g", "802-11-wireless-security.psk", "connection", "show", name],
                    encoding="utf-8",
                ).strip()
                if password:
                    networks.append((name, password))
            except:
                continue
    except Exception as e:
        console.print(f"[red]Error reading Linux Wi-Fi (is nmcli installed?): {e}[/red]")
    return networks

def get_known_wifi():
    os_name = platform.system()
    with console.status("[bold cyan]Scraping system Wi-Fi profiles...", spinner="dots"):
        if os_name == "Windows":
            return get_wifi_windows()
        elif os_name == "Linux":
            return get_wifi_linux()
        else:
            return []

# file and plist logic

def find_itlwm_info_plist(start_dir: Path) -> Path:
    for plist_path in start_dir.rglob("itlwm.kext/Contents/Info.plist"):
        return plist_path
    return None

def write_to_plist(plist_path, selected_networks):
    # backkitupp
    backup_path = plist_path.with_suffix(".plist.bak")
    shutil.copy2(plist_path, backup_path)
    
    with open(plist_path, "rb") as f:
        plist = plistlib.load(f)

    wifi_dict = {}
    for idx, (ssid, password) in enumerate(selected_networks, start=1):
        wifi_dict[f"WiFi_{idx}"] = {"ssid": ssid, "password": password}

    # IOKitPersonalities -> itlwm -> WiFiConfig
    if "IOKitPersonalities" in plist and "itlwm" in plist["IOKitPersonalities"]:
        plist["IOKitPersonalities"]["itlwm"]["WiFiConfig"] = wifi_dict
    else:
        # fallback structure
        console.print("[yellow]Warning: Standard itlwm structure not found. Creating keys...[/yellow]")
        if "IOKitPersonalities" not in plist: plist["IOKitPersonalities"] = {}
        if "itlwm" not in plist["IOKitPersonalities"]: plist["IOKitPersonalities"]["itlwm"] = {}
        plist["IOKitPersonalities"]["itlwm"]["WiFiConfig"] = wifi_dict

    with open(plist_path, "wb") as f:
        plistlib.dump(plist, f)

# thinkdifferent ui

def main():
    console.print(Panel.fit(
        "[bold cyan]Itlwmjector • wi-fi injector[/bold cyan]\n"
        "[dim]Select profiles to bake into your kext[/dim]",
        border_style="cyan"
    ))

    if platform.system() != "Windows" and os.getuid() != 0:
        console.print("[bold red]ERROR:[/bold red] You must run this script with [bold]sudo[/bold] to read passwords on Linux.")
        sys.exit(1)

    # find kext
    script_dir = Path(__file__).resolve().parent
    plist_path = find_itlwm_info_plist(script_dir)
    
    if not plist_path:
        console.print(f"[red]❌ itlwm.kext not found in {script_dir} or subfolders.[/red]")
        sys.exit(1)
    
    console.print(f"[green]📍 Found:[/green] [dim]{plist_path}[/dim]\n")

    # get wifi anywhere you go

    all_networks = get_known_wifi()
    if not all_networks:
        console.print("[yellow]No Wi-Fi networks with saved passwords were found on this system.[/yellow]")
        sys.exit(1)

    # interact

    table = Table(title="Known Wi-Fi Profiles", box=box.SIMPLE_HEAVY)
    table.add_column("#", justify="right", style="bold")
    table.add_column("SSID", style="cyan")
    table.add_column("Password", style="green")

    for idx, (ssid, password) in enumerate(all_networks, start=1):
        table.add_row(str(idx), ssid, "*" * len(password))

    console.print(table)
    
    choice = Prompt.ask(
        "\nEnter numbers to save (e.g. '1,3,4') or 'all'",
        default="all"
    )

    selected = []
    if choice.lower() == "all":
        selected = all_networks
    else:
        try:
            indices = [int(i.strip()) - 1 for i in choice.split(",")]
            selected = [all_networks[i] for i in indices if 0 <= i < len(all_networks)]
        except:
            console.print("[red]Invalid selection. Exiting.[/red]")
            sys.exit(1)

    if not selected:
        console.print("[yellow]No networks selected. Nothing to do.[/yellow]")
        sys.exit(0)

    # confirm and append to kext
    console.print(f"\n[bold blue]Selected {len(selected)} networks for injection.[/bold blue]")
    if Confirm.ask("Ready to write to Info.plist? (Backup will be created)"):
        write_to_plist(plist_path, selected)
        console.print("\n[bold green]✅ Successfully injected Wi-Fi profiles![/bold green]")
    else:
        console.print("[yellow]Aborted.[/yellow]")

if __name__ == "__main__":
    main()
