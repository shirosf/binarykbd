/*
 * UHID keyboard
 * Copyright (c) 2023 Shiro Ninomiya <shirosf@gmail.com>
 *
 * The code is released under GPL-2.0 license.
 * This program is based on 'uhid-example.c' in the Linux kernel source.
 *
 */
/*
 * UHID Example
 *
 * Copyright (c) 2012-2013 David Herrmann <dh.herrmann@gmail.com>
 *
 * The code may be used by anyone for any purpose,
 * and can serve as a starting point for developing
 * applications using uhid.
 */

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <inttypes.h>
#include <linux/uhid.h>

static unsigned char rdesc[] = {
	0x05, 0x01,	/* USAGE_PAGE (Generic Desktop) */
	0x09, 0x06,	/* USAGE (Keyboard) */
	0xa1, 0x01,	/* COLLECTION (Application) */
	0x05, 0x07,	/* USAGE_PAGE(KeyCodes) */
	0x19, 0xE0,	/* USAGE_MINIMUM (224) */
	0x29, 0xE7,	/* USAGE_MAXIMUM (231) */
	0x15, 0x00,	/* LOGICAL_MINIMUM (0) */
	0x25, 0x01,	/* LOGICAL_MAXIMUM (1) */
	0x75, 0x01,	/* REPORT_SIZE (1) */
	0x95, 0x08,	/* REPORT_COUNT (8) */
	0x81, 0x02,	/* Input (Data,Variable,Absolute);Modifier byte */
	0x95, 0x01,	/* REPORT_COUNT (1) */
	0x75, 0x08,	/* REPORT_SIZE (8) */
	0x81, 0x01,	/* Input (Constant);Reserved byte */
	0x95, 0x05,	/* REPORT_COUNT (5) */
	0x75, 0x01,	/* REPORT_SIZE (1) */
	0x05, 0x08,	/* USAGE_PAGE(for LEDs) */
	0x19, 0x01,	/* USAGE_MINIMUM (1) */
	0x29, 0x05,	/* USAGE_MAXIMUM (5) */
	0x91, 0x02,	/* Output (Data,Var,Abs);LED report */
	0x95, 0x01,	/* REPORT_COUNT (1) */
	0x75, 0x03,	/* REPORT_SIZE (3) */
	0x91, 0x01,	/* Output (Constant);LED report padding */
	0x95, 0x06,	/* REPORT_COUNT (6) */
	0x75, 0x08,	/* REPORT_SIZE (8) */
	0x15, 0x00,	/* LOGICAL_MINIMUM (0) */
	0x25, 0x65,	/* USAGE_MAXIMUM (101) */
	0x05, 0x07,	/* USAGE_PAGE(Key Codes) */
	0x19, 0x00,	/* USAGE_MINIMUM (0) */
	0x29, 0x65,	/* USAGE_MAXIMUM (101) */
	0x81, 0x00,	/* Input (Data, Array); Key array(6 bytes) */
	0xc0,		/* END_COLLECTION */
};

static int uhid_write(int fd, const struct uhid_event *ev)
{
	ssize_t ret;

	ret = write(fd, ev, sizeof(*ev));
	if (ret < 0) {
		fprintf(stderr, "Cannot write to uhid: %m\n");
		return -errno;
	} else if (ret != sizeof(*ev)) {
		fprintf(stderr, "Wrong size written to uhid: %ld != %lu\n",
			ret, sizeof(ev));
		return -EFAULT;
	} else {
		return 0;
	}
}

static int create(int fd)
{
	struct uhid_event ev;

	memset(&ev, 0, sizeof(ev));
	ev.type = UHID_CREATE;
	strcpy((char*)ev.u.create.name, "binary5kbd");
	ev.u.create.rd_data = rdesc;
	ev.u.create.rd_size = sizeof(rdesc);
	ev.u.create.bus = BUS_USB;
	// 15d9 is used in UHID Example, so I borrow the same ID here.
	ev.u.create.vendor = 0x15d9;
	// I made up some product number
	ev.u.create.product = 0x2323;
	ev.u.create.version = 0;
	ev.u.create.country = 0;
	return uhid_write(fd, &ev);
}

static void destroy(int fd)
{
	struct uhid_event ev;

	memset(&ev, 0, sizeof(ev));
	ev.type = UHID_DESTROY;

	uhid_write(fd, &ev);
}

static int event(int fd)
{
	struct uhid_event ev;
	ssize_t ret;

	memset(&ev, 0, sizeof(ev));
	ret = read(fd, &ev, sizeof(ev));
	if (ret == 0) {
		fprintf(stderr, "Read HUP on uhid-cdev\n");
		return -EFAULT;
	} else if (ret < 0) {
		fprintf(stderr, "Cannot read uhid-cdev: %m\n");
		return -errno;
	} else if (ret != sizeof(ev)) {
		fprintf(stderr, "Invalid size read from uhid-dev: %ld != %lu\n",
			ret, sizeof(ev));
		return -EFAULT;
	}

	switch (ev.type) {
	case UHID_START:
		fprintf(stderr, "UHID_START from uhid-dev\n");
		break;
	case UHID_STOP:
		fprintf(stderr, "UHID_STOP from uhid-dev\n");
		break;
	case UHID_OPEN:
		fprintf(stderr, "UHID_OPEN from uhid-dev\n");
		break;
	case UHID_CLOSE:
		fprintf(stderr, "UHID_CLOSE from uhid-dev\n");
		break;
	case UHID_OUTPUT:
		fprintf(stderr, "UHID_OUTPUT from uhid-dev\n");
		break;
	case UHID_OUTPUT_EV:
		fprintf(stderr, "UHID_OUTPUT_EV from uhid-dev\n");
		break;
	default:
		fprintf(stderr, "Invalid event from uhid-dev: %u\n", ev.type);
	}

	return 0;
}

static int send_event(int fd, uint8_t mod, uint8_t scancode)
{
	struct uhid_event ev;
	memset(&ev, 0, sizeof(ev));
	ev.type = UHID_INPUT2;
	ev.u.input2.size = 8;
        //data[0]: b7..b0
	//  RightGUI,RightAlt,RightShift,RightCtl,LeftGui,LeftAlt,LeftShift,LeftCtr
	ev.u.input2.data[0] = mod;
	ev.u.input2.data[2] = scancode;
	if(uhid_write(fd, &ev)){return -1;}
	ev.u.input2.data[0] = 0;
	ev.u.input2.data[2] = 0;
	return uhid_write(fd, &ev);
}

static uint8_t scancode(uint8_t key)
{
 	switch(key){
	case '0':
		return 0x27;
	case 13: // return
		return 0x28;
	case 27: // escape
		return 0x29;
	case 8: // BS
		return 0x2a;
	case 9: // TAB
		return 0x2b;
 	case 37: // left
		return 0x50;
	case 38: // up
		return 0x52;
	case 39: // right
		return 0x4f;
	case 40: // down
		return 0x51;
	case 33: // PageUp
		return 0x4b;
	case 34: // PageDown
		return 0x4e;
	case 186: // semi-colon
		return 0x33;
	case 187: // equal
		return 0x2e;
	case 188: // comma
		return 0x36;
	case 189: // dash
		return 0x2d;
	case 190: // period
		return 0x37;
	case 191: // forward slash /
		return 0x38;
	case 192: // grave accent `
		return 0x35;
	case 219: // open bracket [
		return 0x2f;
	case 220: // back slash
		return 0x31;
	case 221: // close bracket ]
		return 0x30;
	case 222: // single quote '
		return 0x34;
	default:
		if(key>='A' && key<='Z'){
			return key-'A'+0x04;
		}else if(key>='1' && key<='9'){
			 return key-'1'+0x1e;
		}else if(key>=1 && key<=26){
			return key+0x03;
		}else if(key>=112 && key<=123){ // F1..F12
			return key-112+0x3a;
		}
		return 0;
	}
        return 0;
}

static int keyboard(int fd)
{
	char buf[8];
	ssize_t ret, i;

	ret = read(STDIN_FILENO, buf, sizeof(buf));
	if (ret == 0) {
		fprintf(stderr, "Read HUP on stdin\n");
		return -EFAULT;
	} else if (ret < 0) {
		fprintf(stderr, "Cannot read stdin: %m\n");
		return -errno;
	}
	for (i = 0; i < ret; ++i) {
		switch (buf[i]) {
		case ' ':
			ret = send_event(fd, 0x2, scancode('A'));
			if (ret) return ret;
			break;
		case 'q':
			return -ECANCELED;
		default:
			return 0;
		}
	}

	return 0;
}

int main(int argc, char **argv)
{
	int fd;
	const char *path = "/dev/uhid";
	struct pollfd pfds[2];
	int ret;

	fprintf(stderr, "Open uhid-cdev %s\n", path);
	fd = open(path, O_RDWR | O_CLOEXEC);
	if (fd < 0) {
		fprintf(stderr, "Cannot open uhid-cdev %s: %m\n", path);
		return EXIT_FAILURE;
	}

	fprintf(stderr, "Create uhid device\n");
	ret = create(fd);
	if (ret) {
		close(fd);
		return EXIT_FAILURE;
	}

	pfds[0].fd = STDIN_FILENO;
	pfds[0].events = POLLIN;
	pfds[1].fd = fd;
	pfds[1].events = POLLIN;

	fprintf(stderr, "Press 'q' to quit...\n");
	while (1) {
		ret = poll(pfds, 2, -1);
		if (ret < 0) {
			fprintf(stderr, "Cannot poll for fds: %m\n");
			break;
		}
		if (pfds[0].revents & POLLHUP) {
			fprintf(stderr, "Received HUP on stdin\n");
			break;
		}
		if (pfds[1].revents & POLLHUP) {
			fprintf(stderr, "Received HUP on uhid-cdev\n");
			break;
		}

		if (pfds[0].revents & POLLIN) {
			ret = keyboard(fd);
			if (ret)
				break;
		}
		if (pfds[1].revents & POLLIN) {
			ret = event(fd);
			if (ret)
				break;
		}
	}

	fprintf(stderr, "Destroy uhid device\n");
	destroy(fd);
	return EXIT_SUCCESS;
}
