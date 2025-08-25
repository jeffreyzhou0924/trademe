import { User } from '@prisma/client';
import { Request as ExpressRequest } from 'express';

declare global {
  namespace Express {
    interface Request {
      user?: User;
    }
    
    namespace Multer {
      interface File {
        fieldname: string;
        originalname: string;
        encoding: string;
        mimetype: string;
        size: number;
        destination: string;
        filename: string;
        path: string;
        buffer: Buffer;
      }
    }
  }
}

export interface MulterRequest extends ExpressRequest {
  file?: Express.Multer.File;
  files?: Express.Multer.File[] | { [fieldname: string]: Express.Multer.File[] };
}