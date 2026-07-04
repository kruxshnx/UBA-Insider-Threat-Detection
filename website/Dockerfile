# ──────────────────────────────────────────────────────────────────────────────
# Dockerfile — UBA Frontend (React + Vite, served by nginx)
# Multi-stage: build the static bundle, then serve it behind nginx which also
# reverse-proxies /api to the backend container.
# ──────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app

# Install deps first (layer caching)
COPY package*.json ./
RUN npm ci || npm install

# Build the production bundle. The app calls a RELATIVE "/api" base
# (VITE_API_URL left empty) so nginx can proxy it to the backend — the browser
# never needs to resolve the internal "backend" hostname.
COPY . .
ENV VITE_API_URL=""
RUN npm run build

# ── Serve ──────────────────────────────────────────────────────────────────
FROM nginx:alpine AS serve
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
