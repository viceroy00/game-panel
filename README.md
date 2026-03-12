# 🎮 Game Panel — Private Game Server Management System

A private **Docker-based game server management panel** designed for friends. It includes **Discord authentication, TOTP 2FA, a universal file manager, and Discord notifications**.

---

# Features

* Discord OAuth2 authentication (only Discord server members can register)
* Invite codes for users who do not use Discord
* Local accounts with TOTP 2FA and 8 recovery codes
* Docker container control (start, stop, restart, logs)
* Universal web file manager for mods and configuration
* RBAC permission system per server
* Health checks with downtime alerts and automatic deletion after 7 days
* Discord channel notifications for server status and requests
* SMTP email notifications
* PWA mobile support
* Compatible with Windows Docker Desktop

---

# Access Control Flow

```
Friend joins administrator Discord server
        ↓
Login to Game Panel with Discord
        ↓
Server membership verified
        ↓
Account created automatically
        ↓
2FA setup required

Non‑Discord users → Register using invite code
```

---

# File Management

Instead of building game‑specific mod managers, the panel provides a **universal file explorer**.

```
Server Control → File Manager

/data/
 ├ mods/              Upload mods (.jar etc)
 ├ config/            Edit configuration files
 ├ world/             Download world backups
 └ server.properties  Inline editing
```

All files inside containers can be managed like **Windows Explorer**.

Adding new games does **not require panel code changes**.

---

# Discord Channel Notifications

| Event                    | Color    | Channel |
| ------------------------ | -------- | ------- |
| Server down detected     | Red      | notify  |
| Server start / recovery  | Green    | notify  |
| Deletion warning (day 5) | Orange   | notify  |
| Automatic deletion       | Dark Red | notify  |
| Game server request      | Blue     | request |
| New user registration    | Purple   | notify  |

---

# Quick Start

```
git clone https://your-git-server.example.com/yourname/game-panel.git
cd game-panel
cp .env.example .env

# edit .env configuration

docker compose up -d
```

The initial administrator account is created using:

```
ADMIN_USERNAME
ADMIN_PASSWORD
```

from the `.env` file.

2FA setup is required on the first login.

---

# Game Server Registration Requirements

A container will only appear in the panel if **both conditions are met**.

| Requirement                       | Description                         |
| --------------------------------- | ----------------------------------- |
| `--label game-panel.managed=true` | Marks container as managed by panel |
| `--network game-servers`          | Dedicated Docker network            |

This prevents infrastructure containers from appearing in the server list.

---

# Example Game Server Deployment

Create the network first:

```
docker network create game-servers
```

Minecraft server example:

```
docker run -d \
  --name minecraft-survival \
  --network game-servers \
  --label game-panel.managed=true \
  -e EULA=TRUE \
  -e DISABLE_GUI=true \
  -p 25565:25565 \
  itzg/minecraft-server:java21
```

Valheim server example:

```
docker run -d \
  --name valheim-server \
  --network game-servers \
  --label game-panel.managed=true \
  -p 2456-2458:2456-2458/udp \
  lloesche/valheim-server
```

Docker compose example:

```
labels:
  - "game-panel.managed=true"

networks:
  - game-servers
```

If either the label or network is missing, the container will not appear in the panel.

---

# Discord Bot Setup

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Create a new application
3. Add OAuth redirect URI

```
https://game.example.com/api/auth/discord/callback
```

4. Create a bot and copy the bot token
5. Invite the bot to your Discord server
6. Enable **Server Members Intent**
7. Add the following values to `.env`

```
DISCORD_CLIENT_ID
DISCORD_CLIENT_SECRET
DISCORD_BOT_TOKEN
DISCORD_GUILD_ID
```

To obtain channel IDs:

```
Discord Settings → Advanced → Enable Developer Mode
Right click channel → Copy Channel ID
```

---

# Environment Variables (.env)

## Application

| Variable | Default                                              | Description      |
| -------- | ---------------------------------------------------- | ---------------- |
| APP_NAME | Game Panel                                           | Application name |
| APP_URL  | [https://game.example.com](https://game.example.com) | Public panel URL |
| DEBUG    | false                                                | Debug mode       |

---

## JWT Authentication

| Variable                        | Default  | Description                  |
| ------------------------------- | -------- | ---------------------------- |
| JWT_SECRET                      | required | Random string 64+ characters |
| JWT_ALGORITHM                   | HS256    | Signing algorithm            |
| JWT_ACCESS_TOKEN_EXPIRE_MINUTES | 30       | Access token expiry          |
| JWT_REFRESH_TOKEN_EXPIRE_DAYS   | 7        | Refresh token expiry         |

---

## Database

| Variable     | Default                                  | Description         |
| ------------ | ---------------------------------------- | ------------------- |
| DATABASE_URL | sqlite+aiosqlite:///./data/game_panel.db | Database connection |

---

## SMTP Mail

| Variable    | Description              |
| ----------- | ------------------------ |
| SMTP_HOST   | SMTP server              |
| SMTP_PORT   | SMTP port                |
| SMTP_USER   | SMTP username            |
| SMTP_PASS   | SMTP password            |
| SMTP_FROM   | Sender email             |
| ADMIN_EMAIL | Admin notification email |

---

## Initial Admin

| Variable       | Default  |
| -------------- | -------- |
| ADMIN_USERNAME | admin    |
| ADMIN_PASSWORD | required |

---

## Docker

| Variable      | Default              |
| ------------- | -------------------- |
| DOCKER_SOCKET | /var/run/docker.sock |
| GAME_NETWORK  | game-servers         |

---

## Health Check

| Variable                     | Default |
| ---------------------------- | ------- |
| HEALTHCHECK_INTERVAL_MINUTES | 5       |
| AUTO_DELETE_DAYS             | 7       |
| HEALTHCHECK_NOTIFY           | true    |

---

## Discord OAuth

| Variable              |
| --------------------- |
| DISCORD_CLIENT_ID     |
| DISCORD_CLIENT_SECRET |
| DISCORD_REDIRECT_URI  |
| DISCORD_GUILD_ID      |
| DISCORD_BOT_TOKEN     |

---

## Other Settings

| Variable               | Default |
| ---------------------- | ------- |
| INVITE_CODE_ENABLED    | true    |
| MAX_MOD_UPLOAD_SIZE_MB | 100     |
| PANEL_HTTP_PORT        | 8090    |

---

# Project Structure

```
game-panel/

backend/app/
 ├ auth/
 ├ discord/
 ├ invite/
 ├ containers/
 ├ files/
 ├ rbac/
 ├ requests/
 ├ templates/
 ├ mail/
 ├ scheduler/
 └ config.py

frontend/src/views/
 ├ Login.vue
 ├ Dashboard.vue
 ├ ServerControl.vue
 ├ FileManager.vue
 ├ GameRequest.vue
 ├ AdminUsers.vue
 ├ AdminPermissions.vue
 ├ AdminInvites.vue
 ├ AdminRequests.vue
 └ AdminTemplates.vue

nginx/nginx.conf

docker-compose.yml

docker-compose.test.yml

.env.example

examples/
 └ minecraft.yml
```

---

# Deployment

```
git clone https://git.example.com/game-panel.git
cd game-panel
cp .env.example .env

# edit environment variables

docker compose build --no-cache frontend-build

docker compose up -d --build
```

Database schema migrations run automatically and user data is preserved.

---

# Changelog

## v0.5.3

* Fixed dashboard memory usage display

## v0.5.2

* Improved cache handling for frontend

## v0.5.1

* Fixed file upload compatibility

## v0.5.0

Major request workflow update including multi‑stage approval and template system.

## v0.4.x

Added email verification and Discord role based access control.

## v0.1.0

Initial release including:

* Discord OAuth2 login
* Invite code registration
* TOTP 2FA
* Docker container management
* Universal file manager
* RBAC permissions
* Health checks
* SMTP notifications
* Game server requests
