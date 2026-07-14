FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173

# Dev-server image only. A production multi-stage build (vite build + nginx)
# will be added when deployment is implemented.
CMD ["npm", "run", "dev", "--", "--host"]
