# Gemini config file for my homelab

## Context

This project is used to configure and maintain my homelab. It's based on a project by TechHutTV, some local IPs will be different.

## Network

My local network is in the range 192.168.86.0 and is managed by Google nest router
I got two pihole instances in 192.168.86.79 and 192.168.86.103 to server as dns
Access from outside is secured by nginx proxy manager using subdomains of boflab.duckdns.org. It's hosted on a raspberry pi named bofpi1.lan

## Proxmox

I'm in the process of migrating all services from raspberry pi to VM hosted on a proxmox server. If possible services will run in a docker started from docker compose file under /docker/service_name

Current existing VM:

* servarr
  * contains most of the arr stack to manage media, more info in media folder
  * 192.168.86.
* immich
  * contains immich to manage my photos [https://immich.app/](https://immich.app/)
  * 192.168.86.84
* proxy
  * contains nothing for now, will host Nginx Proxy Manager once migrated
  * 192.168.86.82
* network
  * contains one pi-hole and a homarr instance
  * 192.168.86.79

Also got one LXC container to manage the hard drive and share them in samba

* media.lan
  * 192.168.86.30

## Management

I use ansible to manage all those VM configuration. Everything related to ansible is located in ansible folder
