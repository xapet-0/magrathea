#include <stdarg.h>
#include <stdio.h>
#include <ctype.h>

int ft_scanf(const char *format, ...)
{
    va_list ap;
    va_start(ap, format);
    int count = 0;
    for (int i = 0; format[i]; i++) {
        if (isspace((unsigned char)format[i])) {
            int c;
            while ((c = fgetc(stdin)) != EOF && isspace(c));
            if (c != EOF) ungetc(c, stdin);
            continue;
        }
        if (format[i] != '%') continue;
        i++;
        if (format[i] == 'c') {
            int c = fgetc(stdin);
            if (c == EOF) break;
            char *out = va_arg(ap, char *);
            *out = (char)c;
            count++;
        } else if (format[i] == 's') {
            int c;
            while ((c = fgetc(stdin)) != EOF && isspace(c));
            if (c == EOF) break;
            char *out = va_arg(ap, char *);
            int k = 0;
            out[k++] = (char)c;
            while ((c = fgetc(stdin)) != EOF && !isspace(c))
                out[k++] = (char)c;
            if (c != EOF) ungetc(c, stdin);
            out[k] = '\0';
            count++;
        } else if (format[i] == 'd') {
            int c;
            while ((c = fgetc(stdin)) != EOF && isspace(c));
            if (c == EOF) break;
            int sign = 1;
            if (c == '-' || c == '+') {
                if (c == '-') sign = -1;
                c = fgetc(stdin);
            }
            if (c == EOF || !isdigit(c)) {
                if (c != EOF) ungetc(c, stdin);
                break;
            }
            long val = 0;
            while (c != EOF && isdigit(c)) {
                val = val * 10 + (c - '0');
                c = fgetc(stdin);
            }
            if (c != EOF) ungetc(c, stdin);
            int *out = va_arg(ap, int *);
            *out = (int)(val * sign);
            count++;
        }
    }
    va_end(ap);
    return count;
}
