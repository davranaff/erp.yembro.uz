import createMiddleware from "next-intl/middleware";

import { routing } from "@/i18n/routing";

export default createMiddleware(routing);

export const config = {
  matcher: [
    // Все пути кроме API, статики Next, файлов из public/.
    "/((?!api|_next|_vercel|.*\\..*).*)",
  ],
};
