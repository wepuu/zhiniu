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
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
WORKDIR /app
RUN apk upgrade --no-cache \
    && addgroup -S zhaoniu \
    && adduser -S -G zhaoniu zhaoniu \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
      /usr/local/bin/pnpm /usr/local/bin/pnpx /usr/local/bin/yarn /usr/local/bin/yarnpkg
COPY --from=build --chown=zhaoniu:zhaoniu /app/apps/web/.next/standalone ./
COPY --from=build --chown=zhaoniu:zhaoniu /app/apps/web/.next/static ./apps/web/.next/static
USER zhaoniu
CMD ["node", "apps/web/server.js"]
