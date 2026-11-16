/*
 * Copyright (c) 2014-2026 Bjoern Kimminich & the OWASP Juice Shop contributors.
 * SPDX-License-Identifier: MIT
 */

import path from 'node:path'
import { type Request, type Response, type NextFunction } from 'express'

export function serveKeyFiles () {
  return ({ params }: Request, res: Response, next: NextFunction) => {
    const file = params.file

    const keyDirectory = path.resolve('encryptionkeys')
    const resolvedFile = path.resolve(keyDirectory, file)

    if (!file.includes('/') && resolvedFile.startsWith(`${keyDirectory}${path.sep}`)) {
      res.sendFile(resolvedFile)
    } else {
      res.status(403)
      next(new Error('File names cannot contain forward slashes!'))
    }
  }
}
