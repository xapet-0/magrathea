#include <stdio.h>
void takes_place(int hour)
{
	int h1 = hour % 12 == 0 ? 12 : hour % 12;
	int h2 = (hour + 1) % 12 == 0 ? 12 : (hour + 1) % 12;
	const char *p1 = (hour >= 12 && hour < 24) ? "P.M." : "A.M.";
	const char *p2 = ((hour + 1) % 24 >= 12) ? "P.M." : "A.M.";
	printf("THE FOLLOWING TAKES PLACE BETWEEN %d.00 %s AND %d.00 %s\n", h1, p1, h2, p2);
}
