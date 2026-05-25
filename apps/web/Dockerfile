ARG NODE_BASE_IMAGE=node:22-slim
FROM ${NODE_BASE_IMAGE}

WORKDIR /app

COPY apps/web/package.json apps/web/tsconfig.json apps/web/vite.config.ts apps/web/index.html ./
COPY apps/web/package-lock.json ./package-lock.json
COPY apps/web/src ./src
COPY apps/web/public ./public

RUN npm ci && npm run build

EXPOSE 5173

CMD ["npm", "run", "preview"]
