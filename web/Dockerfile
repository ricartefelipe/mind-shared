FROM node:22-alpine

WORKDIR /app

RUN addgroup -S app && adduser -S -G app app

COPY package.json package-lock.json /app/
RUN npm ci --ignore-scripts

COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json /app/
COPY src /app/src

RUN chown -R app:app /app
USER app

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
