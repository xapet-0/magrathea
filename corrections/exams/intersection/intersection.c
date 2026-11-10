struct s_node { void *content; struct s_node *next; };

void *intersection(struct s_node *lst1, struct s_node *lst2)
{
    for (struct s_node *a = lst1; a; a = a->next) {
        for (struct s_node *b = lst2; b; b = b->next) {
            if (a == b) return a;
        }
    }
    return (void *)0;
}
