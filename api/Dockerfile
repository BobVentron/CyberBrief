FROM node:20-alpine

WORKDIR /app

# Dépendances OS minimales
RUN apk add --no-cache openssl

# Dépendances Node
COPY package.json package-lock.json* ./
RUN npm install --omit=dev

# Génère le client Prisma
COPY prisma ./prisma/
RUN npx prisma generate

# Code source
COPY src ./src/

# Répertoires de données
RUN mkdir -p /app/reports /app/logs

# Non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup \
    && chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

# Lance les migrations Prisma puis l'app
CMD ["sh", "-c", "npx prisma migrate deploy && node src/app.js"]
