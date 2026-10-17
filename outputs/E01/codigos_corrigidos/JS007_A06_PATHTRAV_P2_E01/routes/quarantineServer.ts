/*
 * Copyright (c) 2014-2026 Bjoern Kimminich & the OWASP Juice Shop contributors.
 * SPDX-License-Identifier: MIT
 */

import path from 'node:path'
import { type Request, type Response, type NextFunction } from 'express'

export function serveQuarantineFiles () {
  return ({ params, query }: Request, res: Response, next: NextFunction) => {
    const file = params.file

    if (!file.includes('/')) {
      const basePath = path.resolve('ftp/quarantine/')
      const requestedPath = path.resolve(basePath, file)
      if (requestedPath.startsWith(basePath)) {
        res.sendFile(requestedPath)
      } else {
        res.status(403)
        next(new Error('File names cannot contain forward slashes!'))
      }
    } else {
      res.status(403)
      next(new Error('File names cannot contain forward slashes!'))
    }
  }
}
