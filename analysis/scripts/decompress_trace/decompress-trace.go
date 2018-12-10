package main

import (
	"bufio"
	"bytes"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

func check(e error) {
	if e != nil {
		panic(e)
	}
}

// FEMs
// - Enqueue packet on cc2420::rx. Check if currently overflow on chip, return if so. Check for overflow, and set flag if so.
//   Start HIRQ-321
// - CALLBACK from readDoneLength
// - CALLBACK from readDoneFcf
// - CALLBACK from readDoneAckLength
// - CALLBACK from sendTask (if successfull) which enqueues an ack, and schedules HIRQ-321 if no thread is currently reading packets.

// Thread 0: task loop and tasks
// Thread 321: InterruptFIFOP.fired, PEUSTART readDoneLength.
// PEUSTART will be followed eventually by a call to a HIRQ, which is readDoneLength in the above case. In a signature,
// the PEUSTART line will include the number of cycles it takes before the HIRQ is called, and the normal. That way,
// it can be modelled accurately when a HIRQ is called.
// Thread 1234: readDoneLength - CALLBACK to schedule readDoneFcf
// Thread 2345: readDoneFcf - CALLBACK to scheule readDonePayload
// Thread 3456: readDonePayload - ENQUEUE SRVQUEUE softirq::rx receiveDone_task
// Thread 4567: readDoneAckLength - CALLBACK to schedule readDoneAckPayload
// Thread 5678: readDoneAckPayload

// Services (tasks):
// - task_loop - DEQUEUE SRVQUEUE softirq::rx
// - receiveDone_task - ENQUEUE SRVQUEUE softirq::rx sendTask, ENQUEUE PKTQUEUE ip::sendinfo, ENQUEUE PKTQUEUE ip::sendpacket
// - sendTask - QUEUECOND to decide whether to drop packet or not, DEQUEUE PKTQUEUE ip::sendinfo, DEQUEUE PKTQUEUE ip::sendpacket, ENQUEUE PKTQUEUE cc2420::tx
// - waitForNextPacket - When finished receiving a packet in readDonePayload or readDoneAckPayload, we call this service.
//   The service can be initialized from a callback function in the ns3 model. For instance, IF cc2420::rxfifo.size > 0, THEN CALL waitForNextPacket.
//   Alternatively, the two HIRQs can end with QUEUECOND cc2420::rx, which causes waitForNextPacket to be called if size > 0, or not if size == 0.

// Queues:
// - ip::sendinfo
// - ip::sendpacket
// - softirq::rx
// - cc2420::rx
// - cc2420::tx

// Thread 0 includes all scheduler / tasks. Since these can be interrupted and currently we don't know of a place
// in code where this can be traced, we prepend all event traces in thread 0 with "CTXSW 0 0 [CPU_CYCLES] 0 0 0 0 s". This
// means that no matter where we're interrupted in thread 0, we will still be able to switch back to thread 0 for the events.

var e0 = "HIRQENTRY 0 1 [CPU_CYCLES] 1 0 0 interruptfifop_fired s\n"

var e1 = "TEMPSYNCH 0 1 [CPU_CYCLES] 1 0 1 (TEMP) readDoneLength\n" +
	"PEUSTART 0 1 [CPU_CYCLES] 1 2 0 (TEMP) s\n" +
	"WAITCOMPL 0 1 [CPU_CYCLES] 1 0 1 (TEMP) readDoneLength\n"

var e2 = "TEMPSYNCH 0 1 [CPU_CYCLES] 1 0 1 (TEMP) readDoneLength\n" +
	"PEUSTART 0 1 [CPU_CYCLES] 1 5 0 (TEMP) s\n" +
	"WAITCOMPL 0 1 [CPU_CYCLES] 1 0 1 (TEMP) readDoneLength\n"

var e3 = "HIRQEXIT 0 1 [CPU_CYCLES] 1 0 0 interruptfifop_fired s\n"

var e4 = "HIRQENTRY 0 2 [CPU_CYCLES] 2 0 0 readDoneLength s\n" +
	"COMPL 0 2 [CPU_CYCLES] 1 0 0 (TEMP) readDoneLength\n"

var e5 = "TEMPSYNCH 0 2 [CPU_CYCLES] 2 0 1 (TEMP) readDoneFcf\n" +
	"PEUSTART 0 2 [CPU_CYCLES] 2 3 0 (TEMP) s\n" +
	"WAITCOMPL 0 2 [CPU_CYCLES] 2 0 1 (TEMP) readDoneFcf\n"

var e6 = "HIRQEXIT 0 2 [CPU_CYCLES] 2 0 0 readDoneLength s\n"

var e7 = "HIRQENTRY 0 3 [CPU_CYCLES] 3 0 0 readDoneFcf s\n" +
	"COMPL 0 3 [CPU_CYCLES] 1 0 0 (TEMP) readDoneFcf\n"

var e8 = "TEMPSYNCH 0 3 [CPU_CYCLES] 3 0 1 (TEMP) readDonePayload\n" +
	"PEUSTART 0 3 [CPU_CYCLES] 3 4 0 (TEMP) s\n" +
	"WAITCOMPL 0 3 [CPU_CYCLES] 3 0 1 (TEMP) readDonePayload\n"

var e9 = "HIRQEXIT 0 3 [CPU_CYCLES] 3 0 0 readDoneFcf s\n"

var e10 = "HIRQENTRY 0 4 [CPU_CYCLES] 4 0 0 readDonePayload s\n" +
	"COMPL 0 4 [CPU_CYCLES] 1 0 0 (TEMP) readDonePayload\n"

var e11 = "SRVQUEUE 0 4 [CPU_CYCLES] 0 2 0 receiveDone_task 0\n" +
	"HIRQEXIT 0 4 [CPU_CYCLES] 4 0 0 readDonePayload s\n"

// e39 means that we don't have to record the start of each service / task in each service, but let the scheduler record this event.
var e12 = "" // "SRVQUEUE 0 0 [CPU_CYCLES] 1 2 0 receiveDone_task s\n"

var e13 = "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 receiveDone_task s\n"

var e14 = "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 receiveDone_task s\n"

var e15 = "PKTQUEUE 0 0 [CPU_CYCLES] 0 1 0 receiveDone_task s\n"

var e41 = "SRVQUEUE 0 0 [CPU_CYCLES] 0 2 0 sendTask 0\n"

var e16 = "" // "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 receiveDone_task s\n"

// e39 means that we don't have to record the start of each service / task in each service, but let the scheduler record this event.
var e17 = "" // "SRVQUEUE 0 0 [CPU_CYCLES] 1 2 0 sendTask s\n"

var e18 = "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 sendTask s\n"

var e19 = "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 sendTask s\n"

var e20 = "PKTQUEUE 0 0 [CPU_CYCLES] 1 1 0 sendTask s\n"

// (TEMP) was 2_synch
var e21 = "TEMPSYNCH 0 0 [CPU_CYCLES] 0 0 1 (TEMP) sendDone\n" +
	"PEUSTART 0 0 [CPU_CYCLES] 0 7 0 (TEMP) s\n" +
	"WAITCOMPL 0 0 [CPU_CYCLES] 0 0 1 (TEMP) sendDone\n"

var e22 = "" //"SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 sendTask s\n"

// (TEMP) was 2_synch
var e23 = "HIRQENTRY 0 7 [CPU_CYCLES] 7 0 0 sendDone s\n" +
	"COMPL 0 7 [CPU_CYCLES] 1 0 0 (TEMP) sendDone\n" +
	// "STATECOND 0 7 [CPU_CYCLES] 7 0 0 sendDone s\n" +
	"SRVQUEUE 0 7 [CPU_CYCLES] 0 2 0 sendDone_task s\n" +
	"HIRQEXIT 0 7 [CPU_CYCLES] 7 0 0 sendDone s\n"

var e24 = "HIRQENTRY 0 5 [CPU_CYCLES] 5 0 0 readDoneAckLength s\n" +
	"COMPL 0 5 [CPU_CYCLES] 1 0 0 (TEMP) readDoneAckLength\n"

var e25 = "TEMPSYNCH 0 5 [CPU_CYCLES] 1 0 1 (TEMP) readDoneAck\n" +
	"PEUSTART 0 5 [CPU_CYCLES] 5 6 0 (TEMP) s\n" +
	"WAITCOMPL 0 5 [CPU_CYCLES] 1 0 1 (TEMP) readDoneAckLength\n"

var e26 = "HIRQEXIT 0 5 [CPU_CYCLES] 5 0 0 readDoneAckLength s\n"

var e27 = "" //"TEMPSYNCH 0 6 [CPU_CYCLES] 1 0 1 3_synch readDoneAck\n" +
//"PEUSTART 0 6 [CPU_CYCLES] 6 0 0 readDoneAckPayload s\n" +
//"WAITCOMPL 0 6 [CPU_CYCLES] 1 0 1 3_synch readDoneLength\n"
//"PEUSTART 0 0 [CPU_CYCLES] 6 0 0 readDoneAckPayload s\n"

var e28 = "" // "HIRQEXIT 0 0 [CPU_CYCLES] 6 0 0 readDoneAckLength s\n"

var e29 = "HIRQENTRY 0 0 [CPU_CYCLES] 6 0 0 readDoneAckPayload s\n" +
	"COMPL 0 6 [CPU_CYCLES] 1 0 0 (TEMP) readDoneAckPayload\n"

var e30 = "HIRQEXIT 0 6 [CPU_CYCLES] 6 0 0 readDoneAckPayload s\n"

// e39 means that we don't have to record the start of each service / task in each service, but let the scheduler record this event.
var e31 = "" //"SRVQUEUE 0 0 [CPU_CYCLES] 1 2 0 sendDone_task s\n"

var e32 = "" // "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 sendDone_task s\n"

var e33 = "CTXSW 0 0 [CPU_CYCLES] 0 0 0 0 s\n"

//"SRVENTRY 0 0 [CPU_CYCLES] 0 0 0 scheduler_tasks s\n"// +
//"SRVENTRY 0 0 [CPU_CYCLES] 0 0 0 scheduler_tasks s\n" +
//"LOOPSTART 0 0 [CPU_CYCLES] 0 0 0 2 task_loop\n"

var e34 = "" // "CTXSW 0 0 [CPU_CYCLES] 0 0 0 0 s\n" + "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 task_loop s\n"

var e35 = "" //"QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 task_loop s\n" +
//"LOOPSTART 0 0 [CPU_CYCLES] 0 0 0 4 s\n"

var e36 = "" //"TTWAKEUP 0 0 [CPU_CYCLES] 0 0 0 task_loop_wait s\n" +
//"QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 task_loop_wait s\n" +
//"LOOPRSTART 0 0 [CPU_CYCLES] 0 0 0 4 s\n"

var e37 = "" //"TTWAKEUP 0 0 [CPU_CYCLES] 0 0 0 task_loop_wait s\n" +
//"QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 task_loop_wait s\n" +
//"LOOPSTOP 0 0 [CPU_CYCLES] 0 0 0 4 s\n"

// Need to find a way for task loop to initiate task. SRVQUEUE requires name of service. How do we get the service name here?
var e38 = "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 SERVICE_PLACEHOLDER s\n" + "LOOPRSTART 0 0 [CPU_CYCLES] 0 0 0 2 task_loop\n"

// The 1 in this trace means that we are dequeueing a service. The 2 means that we are dequeueing from queue 2, which is softirq::rx.
var e39 = "SRVQUEUE 0 0 [CPU_CYCLES] 1 2 0 SERVICE_PLACEHOLDER s\n"

var e40 = "PKTQUEUE 0 0 [CPU_CYCLES] 0 3 0 sendTask s\n"

var e42 = ""

var e43 = ""

var e44 = ""

var e45 = ""

var e46 = "" // "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 sendDone_task s\n"

var e47 = "" //"SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 SERVICE_PLACEHOLDER s\n" //"LOOPSTOP 0 0 [CPU_CYCLES] 0 0 0 2 task_loop\n"// + "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 SERVICE_PLACEHOLDER s\n"

var e71 = "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 sendTask empty\n"

var e91 = "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 sendTask notempty\n"

var printed = false

func eid_to_event(e int, cycles int) string {
	res := ""

	switch e {
	case 0:
		res = e0
	case 1:
		res = e1
	case 2:
		res = e2
	case 3:
		res = e3
	case 4:
		res = e4
	case 5:
		res = e5
	case 6:
		res = e6
	case 7:
		res = e7
	case 8:
		res = e8
	case 9:
		res = e9
	case 10:
		res = e10
	case 11:
		res = e11
	case 12:
		res = e12
	case 13:
		res = e13
	case 14:
		res = e14
	case 15:
		res = e15
	case 16:
		res = e16
	case 17:
		res = e17
	case 18:
		res = e18
	case 19:
		res = e19
	case 20:
		res = e20
	case 21:
		res = e21
	case 22:
		res = e22
	case 23:
		res = e23
	case 24:
		res = e24
	case 25:
		res = e25
	case 26:
		res = e26
	case 27:
		res = e27
	case 28:
		res = e28
	case 29:
		res = e29
	case 30:
		res = e30
	case 31:
		res = e31
	case 32:
		res = e32
	case 33:
		res = e33
	case 34:
		res = e34
	case 35:
		res = e35
	case 36:
		res = e36
	case 37:
		res = e37
	case 38:
		res = e38
	case 39:
		res = e39
	case 40:
		res = e40
	case 41:
		res = e41
	case 42:
		res = e42
	case 43:
		res = e43
	case 44:
		res = e44
	case 45:
		res = e45
	case 46:
		res = e46
	case 47:
		res = e47
	}

	adjusted_cycles := strconv.Itoa(cycles * 4)
	return strings.Replace(res, "[CPU_CYCLES]", adjusted_cycles, -1)
}

func main() {
	trace, err := os.Open(os.Args[1])
	check(err)

	defer trace.Close()

	//var last_time int = 0
	scanner := bufio.NewScanner(trace)
	var traceBuffer bytes.Buffer
	traceBuffer.WriteString("EOD\n")
	i := 0
	for scanner.Scan() {
		line := strings.Split(scanner.Text(), " ")
		if len(line) < 2 {
			break
		}
		eid, _ := strconv.Atoi(line[1])
		i += 1
		cycles, _ := strconv.Atoi(line[0])
		cycles -= 40 * i
		fmt.Println(eid)
		traceBuffer.WriteString(eid_to_event(eid, cycles))
		//last_time = cycles
	}
	// Trace 47 ends the task loop and service; relevant in TinyOS, but not in T-Rex
	//traceBuffer.WriteString(eid_to_event(47, last_time))
	traceBuffer.WriteString("H		\n")

	if err := scanner.Err(); err != nil {
		log.Fatal(err)
	}

	err = ioutil.WriteFile("output/processed-"+filepath.Base(trace.Name()), traceBuffer.Bytes(), 0644)
	check(err)
}
