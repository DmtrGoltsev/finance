ARG NODE_BASE_IMAGE
FROM ${NODE_BASE_IMAGE}
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts && npm cache clean --force
COPY gateway ./gateway
USER node
CMD ["node", "gateway/server.mjs"]
