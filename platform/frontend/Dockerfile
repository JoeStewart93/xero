FROM node:24-alpine AS build

ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_DEFAULT_C2_BASE_URL=http://localhost:8001
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_DEFAULT_C2_BASE_URL=$VITE_DEFAULT_C2_BASE_URL

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 3000
