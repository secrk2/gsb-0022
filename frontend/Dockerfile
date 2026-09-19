FROM node:20-alpine AS build
WORKDIR /build
# 先拷贝清单，利用构建层缓存依赖
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
ENV TZ=Asia/Shanghai
RUN apk add --no-cache tzdata
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/dist /usr/share/nginx/html
EXPOSE 8121
