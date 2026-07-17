==========================================================
  CORP HEIST — Deploy Checklist & SSH Guide
==========================================================

PRE-DEPLOY (check all):
  [ ] Git repo clean (git status)
  [ ] All tests pass (python tests/test_protocol.py)
  [ ] All tests pass (python tests/test_bridge.py)
  [ ] Landing page works (open landing.html)
  [ ] Wealth card works (open wealth_card.html)
  [ ] Loot render works (open loot_render.html)

DEPLOY (step by step):

  1. Get free VPS:
     - Render.com free tier (750h/mo)
     - OR Oracle Cloud free tier (ARM, 4 cores, 24GB)
     - OR Fly.io free tier (3 shared-cpu-1x)
     - OR any Ubuntu VPS with SSH

  2. SSH into server:
     ssh root@YOUR_IP
     # or: ssh ubuntu@YOUR_IP

  3. Install Python:
     apt update && apt install -y python3 python3-pip git

  4. Clone repo:
     git clone https://github.com/pop31-ai/CORP-HEIST.git
     cd CORP-HEIST

  5. Install deps:
     pip3 install -r requirements.txt aiohttp

  6. Test locally on server:
     python3 tests/test_protocol.py
     python3 tests/test_bridge.py

  7. Start server:
     python3 server_consolidated.py &

  8. Verify:
     curl http://localhost:9000
     curl http://localhost:8080
     curl http://localhost:8080/api/chars

  9. Open ports (firewall):
     ufw allow 9000/tcp
     ufw allow 8080:8109/tcp
     ufw enable

  10. Access:
      Dashboard: http://YOUR_IP:9000
      Cards:     http://YOUR_IP:8080-8109

  11. Set up auto-restart (systemd):
      See SYSTEMD section below

SYSTEMD SERVICE:

  Create /etc/systemd/system/corp-heist.service:

  [Unit]
  Description=CORP HEIST Consolidated Server
  After=network.target

  [Service]
  Type=simple
  User=root
  WorkingDirectory=/root/CORP-HEIST
  ExecStart=/usr/bin/python3 server_consolidated.py
  Restart=always
  RestartSec=5

  [Install]
  WantedBy=multi-user.target

  Then:
  systemctl daemon-reload
  systemctl enable corp-heist
  systemctl start corp-heist
  systemctl status corp-heist

BACKUP:

  # backup char files
  tar -czf backup-$(date +%Y%m%d).tar.gz data/chars/

  # or rsync to another server
  rsync -avz data/chars/ user@backup:/backups/corp-heist/

MONITORING:

  # check server status
  curl http://localhost:9000/api/stats

  # check disk usage
  du -sh data/chars/

  # count char files
  ls data/chars/*.json | wc -l

  # watch logs
  tail -f /var/log/syslog | grep consolidated

ROLLBACK:

  # stop server
  systemctl stop corp-heist

  # restore data
  tar -xzf backup-YYYYMMDD.tar.gz

  # restart
  systemctl start corp-heist

PORTS SUMMARY:

  9000     Command Center (dashboard)
  8080     Wealth Card #1
  8081     Wealth Card #2
  ...
  8109     Wealth Card #30

  Total: 31 TCP ports

FILES:

  server_consolidated.py    Main server (1 process, 31 ports)
  wealth_card.html          Wealth card renderer
  wealth_card_bridge.py     API bridge (standalone)
  wealth_card_cluster.py    Old cluster (deprecated)
  landing.html              Landing page
  loot_render.html          1200-algorithm renderer
  generate_brochure.py      Brochure PDF generator
  protocol.py               Binary protocol v2
  server.py                 Async server (standalone)
  ARCHITECTURE.txt          Old architecture
  SERVER_ARCHITECTURE.txt   Current architecture
  DEPLOY.md                 This file
  requirements.txt          Python deps
  .github/workflows/ci.yml  CI/CD
  tests/test_protocol.py    57 protocol tests
  tests/test_bridge.py      26 bridge tests
  content/                  All content + marketing
  data/chars/               User JSON files (runtime)

COST: 0₽

COMPLIANCE:
  14-ФЗ (Advertising)
  39-ФЗ (Securities)
  152-ФЗ (Personal Data)
  149-ФЗ (Information)
  Age: 12+ | Rating: 0+
