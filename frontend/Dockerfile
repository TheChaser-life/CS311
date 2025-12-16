FROM node:18-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci

COPY . .

RUN npm run build

# Stage 2: Run with Nginx
FROM nginx:alpine
# Copy file build vào thư mục web của Nginx
COPY --from=builder /app/dist /usr/share/nginx/html
# Copy file cấu hình Nginx (Sẽ tạo ở bước dưới)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
