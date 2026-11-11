/*
 * Copyright (c) 2014-2026 Bjoern Kimminich & the OWASP Juice Shop contributors.
 * SPDX-License-Identifier: MIT
 */

import path from 'node:path'
import { type Request, type Response, type NextFunction } from 'express'

export function serveQuarantineFiles () {
  return ({ params, query }: Request, res: Response, next: NextFunction) => {
    const file = params.file

    const quarantinePath = path.resolve('ftp/quarantine/')
    const filePath = path.resolve(quarantinePath, file)
    const relativePath = path.relative(quarantinePath, filePath)

    if (!file.includes('/') && !relativePath.startsWith('..' + path.sep) && relativePath !== '..' && !path.isAbsolute(relativePath)) {
      res.sendFile(filePath)
    } else {
      res.status(403)
      next(new Error('File names cannot contain forward slashes!'))
    }
  }
}
