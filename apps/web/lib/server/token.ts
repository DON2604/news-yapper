import "@/lib/server/env";
import { SignJWT } from "jose";

const ISSUER = "aks-web";
const AUDIENCE = "aks-api";

function secret(): Uint8Array {
  const value = process.env.API_JWT_SECRET;
  if (!value || value.length < 16) {
    throw new Error("API_JWT_SECRET is missing - run `npm run setup` at the repository root.");
  }
  return new TextEncoder().encode(value);
}

/** Short-lived token the Next.js server presents to FastAPI. Never sent to the browser. */
export async function mintApiToken(subject: string, scope: "user" | "internal" = "user"): Promise<string> {
  return new SignJWT({ scope })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(subject)
    .setIssuer(ISSUER)
    .setAudience(AUDIENCE)
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(secret());
}
