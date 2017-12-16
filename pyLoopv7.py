import pyaudio
import wave
import sys, os
import multiprocessing
import serial
import struct

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "output_"

def record(wavFile, lock, channel, event, device):
    event.wait()
    lock.acquire()
    try:
        p = pyaudio.PyAudio()

        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        input_device_index=device,
                        frames_per_buffer=CHUNK)

        print("* recording channel "+str(channel))

        frames = []

        while event.is_set():
            data = stream.read(CHUNK)
            frames.append(data)

        print("* done recording")

        stream.stop_stream()
        stream.close()
        p.terminate()

        wf = wave.open(wavFile, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
    finally:
        lock.release()

def recordDummy(wavFile, device):

    p = pyaudio.PyAudio()
    wf = wave.open(wavFile, "rb")

    def callback(in_data, frame_count, time_info, status):
        data = wf.readframes(frame_count)
        return (data, pyaudio.paContinue)

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device,
                    frames_per_buffer=CHUNK,
                    stream_callback=callback)

    frames = []

    for i in range(0, int(RATE / CHUNK * 0.5)):
        data = stream.read(CHUNK)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(wavFile, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

def play(wavFiles, lock, device):
    # lock.acquire()
    try:
        wfs = []
        for file in wavFiles:
            wfs.append(wave.open(file, 'rb'))

        p = pyaudio.PyAudio()
        streams = []
        for wf in wfs:
            def callback(in_data, frame_count, time_info, status):
                data = wf.readframes(frame_count)
                return (data, pyaudio.paContinue)

            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output_device_index=device,
                            output=True,
                            stream_callback=callback)
            streams.append(stream)

            stream.start_stream()

        for stream in streams:
            stream.stop_stream()
            stream.close()

        p.terminate()
    finally:
        # lock.release()

def loopWavs(files, locks, device):

    # pool = multiprocessing.Pool(4)
    # pool.map(play, )
    jobs = []
    for i in range(4):
        jobs.append(multiprocessing.Process(target=play, args=(files[i], locks[i], device)))
    for j in jobs:
        j.start()
    for j in jobs:
        j.join()

def recordSerial(files, locks, keepPlaying, device):
    events = [multiprocessing.Event() for e in range(4)]
    channel = int()
    msg = int()

    recJobs = [multiprocessing.Process(target=record, args=(files[i], locks[i], i, events[i], device)) for i in range(4)]

    # with serial.Serial('/dev/ttyACM0', 57600) as ser:
    with serial.Serial('COM6', 57600) as ser:

        while True:
            x = ser.read(3)
            strx = x.decode("ascii")
            print(strx)
            ser.write(x)
            channel = int(strx[0])
            msg = int(strx[1])

            if channel == 0:
                #Stop playing by setting event
                keepPlaying.set()
            else:
                channel = channel - 1
                if msg==0:
                    # record(files[channel], locks[channel], channel)
                    events[channel].set()
                    recJobs[channel].start()
                elif msg==2:
                    events[channel].clear()
                    #Join and restart the job
                    recJobs[channel].join()


if __name__=="__main__":
    keepPlaying = multiprocessing.Event()
    files = []
    for i in range(4):
        files.append(WAVE_OUTPUT_FILENAME + str(i) + ".wav")
    locks = []

    for i in range(4):
        lock = multiprocessing.Lock()
        locks.append(lock)

    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_host_api_device_index(0, i)
        print(info)
        if "Microphone" in info['name'] and info["maxInputChannels"] > 0:
            device = i
        if "Speaker/HP" in info['name']:
            outDevice = i

    for i in range(4):
        if not os.path.isfile(files[i]):
            recordDummy(files[i], device)


    # recProc = multiprocessing.Process(target=recordSerial, args=(files, locks, keepPlaying, device))
    # recProc = multiprocessing.Process(target=recordSerial, args=(files, locks, keepPlaying))
    # recProc.start()


    while not keepPlaying.is_set():
        loopWavs(files, locks, outDevice)


