# Build stage
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage — serve via Nginx (handled by the nginx service)
# This image only produces the dist/ artifact
FROM scratch AS dist
COPY --from=builder /app/dist /dist
