FROM node:18-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# Build with the backend URL pointing to the Docker service name
ENV VITE_API_BASE=http://localhost:8000
RUN npm run build

# Serve with a lightweight static server
FROM nginx:alpine

# Custom nginx config to proxy API calls to backend
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 5173

CMD ["nginx", "-g", "daemon off;"]
