FROM node:20-alpine
WORKDIR /app
COPY apps/trace-ui/package.json apps/trace-ui/package-lock.json* ./
RUN npm ci || npm install
COPY apps/trace-ui/ ./
COPY content/ ./content/
EXPOSE 3000
CMD ["npm", "run", "dev"]
