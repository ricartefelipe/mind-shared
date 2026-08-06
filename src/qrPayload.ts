export function buildQrPayload(amountCents: number, pixKey: string): string {
  return `MINDPIX|v1|${pixKey}|${amountCents}`
}
