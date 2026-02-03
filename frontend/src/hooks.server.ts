import type { Handle } from '@sveltejs/kit';

/**
 * Server hooks for adding security and feature policy headers.
 *
 * The Permissions-Policy header is required to allow camera access
 * for QR code scanning on mobile devices.
 */
export const handle: Handle = async ({ event, resolve }) => {
    const response = await resolve(event);

    // Allow camera access for QR scanning
    // This is required because some reverse proxies or hosting providers
    // may set restrictive Permissions-Policy headers by default
    response.headers.set(
        'Permissions-Policy',
        'camera=(self), microphone=(self), geolocation=(self)'
    );

    return response;
};
