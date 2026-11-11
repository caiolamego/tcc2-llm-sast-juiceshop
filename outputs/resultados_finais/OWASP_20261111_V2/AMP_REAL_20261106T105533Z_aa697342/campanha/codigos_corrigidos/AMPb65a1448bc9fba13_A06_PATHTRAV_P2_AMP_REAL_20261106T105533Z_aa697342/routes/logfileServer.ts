/*
 * Copyright (c) 2014-2026 Bjoern Kimminich & the OWASP Juice Shop contributors.
 * SPDX-License-Identifier: MIT
 */

import path from 'node:path'
import { type Request, type Response, type NextFunction } from 'express'

export function serveLogFiles () {
  return ({ params }: Request, res: Response, next: NextFunction) => {
    const file = params.file

    const logsDirectory = path.resolve('logs')
    const resolvedFile = path.resolve(logsDirectory, file)
    const relativeFile = path.relative(logsDirectory, resolvedFile)

    if (relativeFile && !relativeFile.startsWith(`..${path.sep}`) && relativeFile !== '..' && !path.isAbsolute(relativeFile)) {
      res.sendFile(resolvedFile)
    } else {
      res.status(403)
      next(new Error('File names cannot contain forward slashes!'))
    }
  }
}
