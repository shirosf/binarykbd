all: uhid-binary5kbd

uhid-binary5kbd: uhid-binary5kbd.c
	$(CC) -Wall -o $@ $^
