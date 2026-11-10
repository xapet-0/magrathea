int count_words_exam(const char *str)
{
	int i = 0, c = 0;
	while (str && str[i])
	{
		while (str[i] == ' ' || str[i] == '\t') i++;
		if (str[i]) c++;
		while (str[i] && str[i] != ' ' && str[i] != '\t') i++;
	}
	return (c);
}
