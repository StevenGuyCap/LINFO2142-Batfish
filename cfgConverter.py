# ----------------------------------------------------------------------------------------------------------------
#
# Translation script for converting our configuration files into CUMULUS like recognized by our batfish notebook
#
# /!\ using this script on other configuration that wasn't used in the notebook, doesn't guarantee to lead to
# a recognized format. This translation script is specific to the files we used. While working well on other files
# some of them could be tricky and create incorrect formats.
#
# ----------------------------------------------------------------------------------------------------------------

# Import for the script
import numpy as np
import os
import sys


def get_txt_files(dir_name: str):
    """
    Function allowing to discover all the txt files contained inside a directory

    Args:
        dir_name: string representing the name of the directory

    Returns:
        a numpy array containing strings of the name of the txt files contained inside the directory
    """
    tmp = np.array(os.listdir(dir_name))
    out = np.array([t if t[-4:] == ".txt" else "" for t in tmp])
    return out[out != ""]


def convert_dir(lst_files, out="", suf="", ignore=("S1.txt", "S2.txt", "S3.txt", "S4.txt")):
    """
    Function used to convert a whole directory into a batfish-readable format by calling multiple times
    the txt_to_cfg function on a list of files.

    Args:
        lst_files: array containing the list of files we want to convert
        out: string representing the out argument of txt_to_cfg
        suf: string representing the suf argument of txt_to_cfg
        ignore: array indicating files we don't want to convert
    """
    for t in lst_files:
        if t in ignore:
            continue
        else:
            txt_to_cfg(t, out, suf)


def length_to_mask(prefix_size):
    """
    Converts an IPv4 prefix length to a mask. For example, a prefix of size 21 correponds to the mask 255.255.248.0

    Args:
        prefix_size: size of the prefix to convert

    Returns: string representing an IPv4 mask

    """
    ip = [0, 0, 0, 0]
    for i in range(prefix_size // 8):
        ip[i] = 255
    if (prefix_size // 8) < 4:
        ip[prefix_size // 8] = int((('1' * (prefix_size % 8)) + ('0' * (8 - (prefix_size % 8)))), 2)
    return str(ip[0]) + "." + str(ip[1]) + "." + str(ip[2]) + "." + str(ip[3])


def txt_to_cfg(name, out="", suf=""):
    """
    Converts a mini-internet configuration file into a suitable format to be analyzed by batfish.
    The default configurations files of the mini internet project use FRRouting. This functions converts it into a
    cumulus format, which batfish can recognize.
    
    The converted file will be named {out}{base}{suf}.cfg with
    -out being an argument of the function
    -base being the base name of the file (without the extension)
    -suf being another argument
    
    Args:
        name: string representing the name of the file we want to convert
        out: string used to name the written file 
        suf: string used to name the written file

    Returns:

    """

    # Getting the base name
    base = name.split(".")[0]
    host = ""

    # Lines to write inside the cfg file
    frr_lines = [""]
    int_lines = []

    # Getting the lines of the current txt file
    with open(name, "r") as file:
        lines = file.readlines()[4:]

    # Going through the lines of the file
    i = 0
    while i < len(lines):
        # Getting the instruction words at that line
        cmds = lines[i].strip().split(" ")

        # Instantiating the hostname for frr
        if cmds[0] == "hostname":
            host = cmds[1] + suf
            frr_lines.append(lines[i].strip() + suf + "\n")
            i += 1

        # Ignore if the command is a ospf6 configuration
        elif cmds[0] == "router" and cmds[1] == "ospf6":
            while lines[i] != "!\n":
                i += 1

        # Convert the frr interfaces to cumulus interfaces
        elif cmds[0] == "interface":
            iface_name = cmds[1]
            toAdd = f"auto {iface_name}\n"
            i += 1
            # Going through the lines of this interface
            while lines[i] != "!\n":
                ips = lines[i].strip().split(" ")
                # IPv4 address
                if ips[0] == "ip" and ips[1] == "address":
                    toAdd += f"iface {iface_name} inet static\n  address {ips[2]}\n"
                # OSPF cost
                elif ips[0] == "ip" and ips[1] == "ospf":
                    frr_lines += f"interface {iface_name}\n ip {ips[1]} {ips[2]} {ips[3]}\n!\n"
                i += 1
            # Add to cumulus part
            toAdd += "\n"
            int_lines.append(toAdd)

        # Ignore the rpki instructions
        elif cmds[0] == "rpki":
            while lines[i] != "!\n":
                i += 1

        # Translate bgp community-list
        elif cmds[0] == "bgp" and cmds[1] == "community-list":
            # "expanded" in place of name
            if cmds[2] == "expanded":
                frr_lines.append(f"{cmds[0]} {cmds[1]} expanded {cmds[3]} {cmds[6]} {cmds[7]}\n")
            else:
                frr_lines.append(f"{cmds[0]} {cmds[1]} standard {cmds[2]} {cmds[5]} {cmds[6]}\n")
            i += 1

        # Change the name format of the as-path for BGP
        elif cmds[0] == "bgp" and cmds[1] == "as-path":
            frr_lines.append(f"{cmds[0]} {cmds[1]} {cmds[2]} as_path_{cmds[3]} {cmds[4]} {cmds[5]}\n")
            i += 1

        # Use the new formatted name for the as-path inside match as-path
        elif cmds[0] == "match" and cmds[1] == "as-path":
            frr_lines.append(f" {cmds[0]} {cmds[1]} as_path_{cmds[2]}\n")
            i += 1

        # Ignore the instruction "set community none"
        elif cmds[0] == "set" and cmds[1] == "community" and cmds[2] == "none":
            i += 1

        # Ignore "match rpki"
        elif cmds[0] == "match" and cmds[1] == "rpki":
            i += 1

        # Ignore "debug" instructions
        elif cmds[0] == "debug":
            i += 1

        # Ignore "router-info" instructions
        elif cmds[0] == "router-info":
            i += 1

        # Ignore "ipv6 route" instructions
        elif cmds[0] == "ipv6" and cmds[1] == "route":
            i += 1

        # Every line different from the previous one is appended if not ignored
        elif lines[i] != frr_lines[len(frr_lines) - 1]:
            frr_lines.append(lines[i])
            i += 1

        # Ignore repeated lines
        else:
            i += 1

    # Final write to the output file
    with open(f"{out}{base}{suf}.cfg", "w") as file:
        file.write(f"{host}\n# This file describes the network interfaces\n")
        file.writelines(int_lines)  # Write the "cumulus" lines
        file.write("# ports.conf --\n\n")  # Write a line for the ports configuration
        file.writelines(frr_lines)  # Write the frr routing lines left

    # Final return
    return True


def usage():
    print("USAGE")
    print("$python3 cfgConverter.py [-h] [-s] [-o] <directory>")
    print()
    print("DESCRIPTION")
    print("Converts all .txt files in a folder into suitable .cfg files for batfish")
    print("The conversion performed is from FRRouting to CUMULUS format")
    print("The converted files are of the form : {out}{base_filename}{suf}.cfg, with base_filename being the original name of the file (without the .txt extension) and out/suf being two parameters of this command")
    print()
    print("OPTIONS")
    print("-h : displays help about this command")
    print("-o : allows to specify the {out} part of the converted files names. By default, this argument is an empty string")
    print("-s : allows to specify the {suf} part of the converted files names. By default, this argument is an empty string")
    return


if __name__ == "__main__":
    # Base configuration
    fls = get_txt_files('.')
    s = ""
    o = ""
    h = False

    # Args parsing
    argc = 1
    while argc < len(sys.argv) :
        if sys.argv[argc] == '-h' or sys.argv[argc] == '--help':
            usage()
            argc = len(sys.argv)
        elif sys.argv[argc] == '-s':
            s = sys.argv[argc+1]
            argc += 2
        elif sys.argv[argc] == '-o':
            o = sys.argv[argc+1]
            argc += 2
        else:
            h = True
            print("Bad parameter. Showing the help and exiting")
            usage()
            argc = len(sys.argv)

    # Running the translater
    if not h:
        try:
            convert_dir(fls, out=o, suf=s)
            print("Conversion successful")
        except Exception as err:
            print(f"An error occured inside the translation of this directory : {err}")
