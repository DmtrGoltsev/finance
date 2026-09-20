FROM node:22.22.0-alpine3.23
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts && npm cache clean --force
COPY gateway ./gateway
USER node
CMD ["node", "gateway/server.mjs"]
