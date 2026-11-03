/**
 * Identificador end-to-end no formato do arranjo PIX do Banco Central: `E` + ISPB (8 dígitos) + data e hora UTC
 * `yyyyMMddHHmm` + 11 alfanuméricos, 32 caracteres. Mesmo formato que SpringMind e vuemind-api geram.
 *
 * O PIX das demonstrações é simulado, então o ISPB é fictício: `99999999` não pertence a nenhum participante do
 * Banco Central.
 */
export const DEMO_ISPB = '99999999'

export const END_TO_END_ID_PATTERN =
  /^E\d{8}\d{4}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])([01]\d|2[0-3])[0-5]\d[a-zA-Z0-9]{11}$/

const ALPHANUMERIC = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'

function utcStamp(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return (
    String(date.getUTCFullYear()) +
    pad(date.getUTCMonth() + 1) +
    pad(date.getUTCDate()) +
    pad(date.getUTCHours()) +
    pad(date.getUTCMinutes())
  )
}

export function createEndToEndId(date: Date = new Date()): string {
  const random = crypto.getRandomValues(new Uint32Array(11))
  const suffix = Array.from(random, (value) => ALPHANUMERIC[value % ALPHANUMERIC.length]).join('')
  return `E${DEMO_ISPB}${utcStamp(date)}${suffix}`
}
