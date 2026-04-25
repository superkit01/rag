FROM docker.m.daocloud.io/library/node:20-alpine

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml* .npmrc ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build

CMD ["pnpm", "run", "start"]
