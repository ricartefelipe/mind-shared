export type PixKeyType = 'EMAIL' | 'CPF' | 'CNPJ' | 'PHONE' | 'RANDOM'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const CPF_PATTERN = /^\d{11}$/
// CNPJ numérico ou alfanumérico: 12 caracteres de A a Z ou 0 a 9 e 2 dígitos verificadores.
const CNPJ_PATTERN = /^[0-9A-Z]{12}\d{2}$/
const PHONE_PATTERN = /^\+?\d{10,13}$/
// Chave aleatória (EVP): UUID, com ou sem hífens.
const RANDOM_PATTERN = /^(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$/
const CNPJ_WEIGHTS = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

function allSame(key: string): boolean {
  return new Set(key).size === 1
}

function cpfDigit(key: string, length: number): number {
  let sum = 0
  for (let i = 0; i < length; i++) sum += Number(key[i]) * (length + 1 - i)
  const rest = (sum * 10) % 11
  return rest === 10 ? 0 : rest
}

function isValidCpf(key: string): boolean {
  if (!CPF_PATTERN.test(key) || allSame(key)) return false
  return cpfDigit(key, 9) === Number(key[9]) && cpfDigit(key, 10) === Number(key[10])
}

// Cada caractere vale o código ASCII menos 48: os números continuam valendo 0 a 9 e as letras, 17 a 42.
function cnpjDigit(key: string, length: number): number {
  let sum = 0
  for (let i = 0; i < length; i++) {
    sum += (key.charCodeAt(i) - 48) * CNPJ_WEIGHTS[CNPJ_WEIGHTS.length - length + i]
  }
  const rest = sum % 11
  return rest < 2 ? 0 : 11 - rest
}

function isValidCnpj(key: string): boolean {
  if (!CNPJ_PATTERN.test(key) || allSame(key)) return false
  return cnpjDigit(key, 12) === Number(key[12]) && cnpjDigit(key, 13) === Number(key[13])
}

export function isValidPixKey(type: PixKeyType, key: string): boolean {
  switch (type) {
    case 'EMAIL':
      return EMAIL_PATTERN.test(key)
    case 'CPF':
      return isValidCpf(key)
    case 'CNPJ':
      return isValidCnpj(key)
    case 'PHONE':
      return PHONE_PATTERN.test(key)
    case 'RANDOM':
      return RANDOM_PATTERN.test(key)
    default: {
      const _exhaustive: never = type
      return _exhaustive
    }
  }
}

export function assertValidPixKey(type: PixKeyType, key: string): void {
  if (!isValidPixKey(type, key)) {
    throw new Error(`INVALID_PIX_KEY: chave PIX inválida para o tipo ${type}.`)
  }
}
