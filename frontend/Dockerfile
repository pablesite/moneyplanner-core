FROM node:20-bookworm-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

# Playwright browser runtime (Chromium) for E2E execution inside the container.
RUN npx playwright install --with-deps chromium

COPY . .

EXPOSE 5173
