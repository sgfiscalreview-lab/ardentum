# Ardentum web — production image. Build context: repository root (needs docs/).
FROM node:26-slim AS deps
WORKDIR /repo/frontend
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci

FROM node:26-slim AS build
WORKDIR /repo/frontend
ARG API_URL=http://backend:8000
ARG NEXT_PUBLIC_SUPABASE_URL=""
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY=""
ARG NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=""
ENV API_URL=$API_URL NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=$NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /repo/frontend/node_modules ./node_modules
COPY frontend ./
COPY docs /repo/docs
RUN npm run build

FROM node:26-slim AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /repo/frontend/.next/standalone ./
COPY --from=build /repo/frontend/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
