#!/bin/bash
echo " ====health Check for my wsl==== "
echo ""

echo "---1.CPU LOAD--- "
uptime
mpstat 1 1 2>/dev/null || top -bn1 | head -n 5

echo ""
echo " ---2.memory Usage ---"
free -m

echo ""
echo "---3.Disk Usage ----"
df -h /

echo""
echo "--- 4. Critical Services Status ---"
echo "docker"
systemctl is-active docker
echo "nginx"
systemctl is-active nginx
echo ""
echo "---5.Listening Ports -----"
ss -lntp | grep -E ':(5000|80|9090|3000)'

