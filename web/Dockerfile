# Contexto de build: a raiz do repositório. O atlas depende do pacote compartilhado
# (`@ricartefelipe/mind-wallet-shared`, `file:..`), que precisa estar dentro da imagem e compilado.
FROM node:22-alpine

WORKDIR /app

RUN addgroup -S app && adduser -S -G app app

COPY package.json package-lock.json tsconfig.json tsconfig.build.json /app/
COPY src /app/src
COPY openapi /app/openapi
RUN npm ci --ignore-scripts && npm run build

WORKDIR /app/web
COPY web/package.json web/package-lock.json /app/web/
RUN npm ci --ignore-scripts

COPY web/index.html web/vite.config.ts web/tsconfig.json web/tsconfig.app.json web/tsconfig.node.json /app/web/
COPY web/src /app/web/src

RUN chown -R app:app /app
USER app

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
