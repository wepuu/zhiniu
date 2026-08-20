FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY apps/web/package.json apps/web/package.json
COPY packages/api-client/package.json packages/api-client/package.json
RUN pnpm install --frozen-lockfile
COPY apps/web ./apps/web
COPY packages/api-client ./packages/api-client
RUN pnpm --filter @zhaoniu/web build

FROM node:22-alpine
ENV NODE_ENV=production
WORKDIR /app
RUN addgroup -S zhaoniu && adduser -S -G zhaoniu zhaoniu && corepack enable
COPY --from=build --chown=zhaoniu:zhaoniu /app /app
USER zhaoniu
CMD ["pnpm", "--filter", "@zhaoniu/web", "start"]
