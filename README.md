
# SF Collab Backend Flask

A collaborative backend API built with Flask, featuring real-time communication via WebSocket, user authentication, and a modular architecture.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Git

### Setup

1. **Clone the repository**

  ```bash
  git clone https://github.com/Success-Framework/sf_collab_backend_flask.git
  cd sf_collab_backend_flask
  ```

2. **Configure environment variables**

  ```bash
  cp env.example .env.development
  cp env.example .env.production
  # Edit both files with your credentials
  ```

3. **Start development environment**

  ```bash
  cd docker
  docker-compose -f docker-compose-dev.yml up -d --build
  cd ..
  ```

4. **Access the API**

  - Development: `http://localhost:5000` for local
  - Production: `https://api.sfcollab.com`

## Key Features

- **Authentication**: JWT-based with OAuth2 (GitHub, Google)
- **Real-time Communication**: WebSocket support via Socket.IO
- **Database**: MySQL with automated migrations
- **Caching**: Redis for sessions and task queues
- **Logging**: Request/response tracking with duration metrics

## Services

| Service | Port | Image |
|---------|------|-------|
| Flask API | 5000 | Custom |
| MySQL | 3306 | mysql:8.0 |
| Redis | 6379 | redis:7 |

## Documentation

- [Deployment Guide](./deploy_documentation.md)
- [Nginx Setup](./nginx_reverse_proxy.md)

## Environment Variables

See `env.example` for all required configuration options including:

- `SECRET_KEY`, `JWT_SECRET_KEY`
- OAuth credentials
- Email configuration
- Database & Redis URLs

## Troubleshooting

```bash
# View container logs
docker logs sfcollab-api

# Restart services
docker-compose -f docker-compose-dev.yml restart

test staging

# Clean up
docker-compose -f docker-compose-dev.yml down
```

fix deploy
