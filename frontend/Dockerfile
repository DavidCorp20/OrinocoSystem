FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine

WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/build ./build

ENV NODE_ENV=production

EXPOSE 8080

CMD ["sh", "-c", "exec serve -s build -l ${PORT:-8080}"]
