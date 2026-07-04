# Build the SvelteKit SPA, then serve it as static files with Caddy.
# The archive data + captures are NOT baked in — they are bind-mounted at
# runtime from the host (/srv/which/{data,captures}).

FROM node:20-alpine AS build
WORKDIR /app
COPY archive-web/package.json archive-web/package-lock.json ./
RUN npm ci
COPY archive-web/ ./
RUN npx vite build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/build /site
