#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>

static void skip_ws(FILE *f)
{
	int c = getc(f);
	while (c == ' ' || c == '\t' || c == '\n' || c == '\r')
		c = getc(f);
	if (c != EOF)
		ungetc(c, f);
}

static int parse_value(FILE *f, char **out, size_t *len, size_t *cap);

static void buf_append(char **out, size_t *len, size_t *cap, char ch)
{
	if (*len + 2 >= *cap)
	{
		*cap = (*cap == 0) ? 256 : (*cap * 2);
		*out = realloc(*out, *cap);
	}
	(*out)[(*len)++] = ch;
	(*out)[*len] = '\0';
}

static int parse_string(FILE *f, char **out, size_t *len, size_t *cap, int *err_tok)
{
	int c = getc(f);
	if (c != '"')
	{
		*err_tok = c;
		return (-1);
	}
	buf_append(out, len, cap, '"');
	while ((c = getc(f)) != EOF)
	{
		if (c == '"')
		{
			buf_append(out, len, cap, '"');
			return (0);
		}
		if (c == '\\')
		{
			int nxt = getc(f);
			if (nxt != '\\' && nxt != '"')
			{
				*err_tok = nxt;
				return (-1);
			}
			buf_append(out, len, cap, '\\');
			buf_append(out, len, cap, (char)nxt);
		}
		else
			buf_append(out, len, cap, (char)c);
	}
	*err_tok = EOF;
	return (-1);
}

static int parse_int(FILE *f, char **out, size_t *len, size_t *cap, int *err_tok)
{
	int c = getc(f);
	if (c == '-')
	{
		buf_append(out, len, cap, '-');
		c = getc(f);
	}
	if (!isdigit(c))
	{
		*err_tok = c;
		return (-1);
	}
	while (isdigit(c))
	{
		buf_append(out, len, cap, (char)c);
		c = getc(f);
	}
	if (c != EOF)
		ungetc(c, f);
	return (0);
}

static int parse_map(FILE *f, char **out, size_t *len, size_t *cap, int *err_tok)
{
	int c = getc(f);
	if (c != '{')
	{
		*err_tok = c;
		return (-1);
	}
	buf_append(out, len, cap, '{');
	skip_ws(f);
	c = getc(f);
	if (c == '}')
	{
		buf_append(out, len, cap, '}');
		return (0);
	}
	if (c != EOF)
		ungetc(c, f);
	while (1)
	{
		skip_ws(f);
		if (parse_string(f, out, len, cap, err_tok) < 0)
			return (-1);
		skip_ws(f);
		c = getc(f);
		if (c != ':')
		{
			*err_tok = c;
			return (-1);
		}
		buf_append(out, len, cap, ':');
		skip_ws(f);
		if (parse_value(f, out, len, cap) < 0)
			return (-1);
		skip_ws(f);
		c = getc(f);
		if (c == '}')
		{
			buf_append(out, len, cap, '}');
			return (0);
		}
		if (c != ',')
		{
			*err_tok = c;
			return (-1);
		}
		buf_append(out, len, cap, ',');
	}
}

static int g_err_tok = 0;

static int parse_value(FILE *f, char **out, size_t *len, size_t *cap)
{
	skip_ws(f);
	int c = getc(f);
	if (c == EOF)
	{
		g_err_tok = EOF;
		return (-1);
	}
	ungetc(c, f);
	if (c == '"')
		return (parse_string(f, out, len, cap, &g_err_tok));
	if (c == '{')
		return (parse_map(f, out, len, cap, &g_err_tok));
	if (c == '-' || isdigit(c))
		return (parse_int(f, out, len, cap, &g_err_tok));
	g_err_tok = getc(f);
	return (-1);
}

int main(void)
{
	char *out = NULL;
	size_t len = 0;
	size_t cap = 0;

	if (parse_value(stdin, &out, &len, &cap) < 0)
	{
		if (g_err_tok == EOF)
			printf("Unexpected end of input\n");
		else
			printf("Unexpected token '%c'\n", (char)g_err_tok);
		free(out);
		return (1);
	}
	skip_ws(stdin);
	int extra = getc(stdin);
	if (extra != EOF)
	{
		printf("Unexpected token '%c'\n", (char)extra);
		free(out);
		return (1);
	}
	printf("%s\n", out ? out : "");
	free(out);
	return (0);
}
